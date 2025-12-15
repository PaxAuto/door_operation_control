import pytest
import rclpy
from std_msgs.msg import Int32, Bool

from door_operation_control.door_node import DoorOperationControl


# ==========================================================
# FIXTURES
# ==========================================================
@pytest.fixture(scope="module")
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node(ros):
    node = DoorOperationControl()
    yield node
    node.destroy_node()

def test_required_subscriptions_exist(node):
    state_subs = node.get_subscriptions_info_by_topic("/state")
    user_inside_subs = node.get_subscriptions_info_by_topic("/user_inside")
    auth_subs = node.get_subscriptions_info_by_topic("/authorization_result")

    assert len(state_subs) == 1
    assert len(user_inside_subs) == 1
    assert len(auth_subs) == 1

# ==========================================================
# INITIAL STATE + STATE 2 (CLOSED) + DEDUPLICATION
# (Merged into ONE test)
# ==========================================================
def test_initial_state_and_state2_closed_and_dedup(node, monkeypatch):
    # Initial state
    assert node.current_status is False
    assert node.state is None

    published = []

    def fake_publish(msg):
        published.append(msg.data)

    monkeypatch.setattr(node.door_pub, "publish", fake_publish)

    # State 2, NOT authorized → door closed
    node.state_callback(Int32(data=2))
    node.auth_callback(Bool(data=False))
    node.user_inside_callback(Bool(data=False))

    assert node.current_status is False

    # Deduplication path
    node.publish_door(False)
    node.publish_door(False)

    assert published == [False]


# ==========================================================
# STATE CALLBACK EDGE CASE
# ==========================================================
def test_state_callback_invalid_payload(node, monkeypatch):
    # Patch logger.warning to avoid ROS2 formatting issue
    monkeypatch.setattr(node.get_logger(), "warning", lambda *args, **kwargs: None)

    class FakeMsg:
        data = "invalid"

    node.state_callback(FakeMsg())

    assert node.state is None


# ==========================================================
# STATE 2 (AUTHORIZED → OPEN)
# ==========================================================
def test_state_2_authorized_opens_door(node):
    node.state_callback(Int32(data=2))
    node.auth_callback(Bool(data=True))
    node.user_inside_callback(Bool(data=False))

    assert node.current_status is True


# ==========================================================
# STATE 3 (INITIAL OPEN + TIMEOUT)
# (Merged into ONE test)
# ==========================================================
def test_state_3_open_and_timeout(node):
    node.state_callback(Int32(data=3))

    # Initial open
    assert node.current_status is True
    assert node.door_open_time is not None

    # Simulate timeout
    node.door_open_time -= 121.0
    node.evaluate_logic()

    assert node.current_status is False
    assert node.state3_expired is True
    assert node.door_open_time is None


# ==========================================================
# STATE RESET LOGIC
# ==========================================================
def test_state3_expired_then_other_state(node):
    node.state_callback(Int32(data=3))
    node.state3_expired = True

    node.state_callback(Int32(data=0))

    assert node.current_status is False
    assert node.state3_expired is False
    assert node.door_open_time is None


# ==========================================================
# TIMER CALLBACK
# ==========================================================
def test_timer_callback_publishes(node, monkeypatch):
    published = []

    def fake_publish(msg):
        published.append(msg.data)

    monkeypatch.setattr(node.door_pub, "publish", fake_publish)

    node.current_status = True
    node.timer_callback()

    assert published[-1] is True
