#!/usr/bin/env python3
# pylint: disable=too-many-function-args

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, Bool


class DoorOperationControl(Node):  # pylint: disable=too-many-instance-attributes
    """ROS2 node to control door operation logic."""

    def __init__(self):
        super().__init__("door_operation_control")

        # -------------------------
        # SUBSCRIPTIONS
        # -------------------------
        self.state_sub = self.create_subscription(
            Int32, "/state", self.state_callback, 10
        )
        self.user_inside_sub = self.create_subscription(
            Bool, "/user_inside", self.user_inside_callback, 10
        )
        self.auth_sub = self.create_subscription(
            Bool, "/authorization_result", self.auth_callback, 10
        )

        # -------------------------
        # PUBLISHER
        # -------------------------
        self.door_pub = self.create_publisher(Bool, "/door_status", 10)

        # -------------------------
        # INTERNAL STATE
        # -------------------------
        self.state = None
        self.user_inside = False
        self.authorization_result = False
        self.door_open_time = None
        self.state3_expired = False
        self.last_published = None
        self.current_status = False

        # Timer for continuous publishing (1 Hz)
        self.timer = self.create_timer(1.0, self.timer_callback)

        self.get_logger().info("✅ Door Operation Control Node started!")

    # ==========================================================
    # CALLBACKS
    # ==========================================================
    def state_callback(self, msg: Int32):
        """Handle updates from /state topic."""
        try:
            self.state = int(msg.data)
        except ValueError:
            self.get_logger().warning(
                "Ignoring non-integer /state payload: %s", msg.data
            )
            return

        self.evaluate_logic()

    def user_inside_callback(self, msg: Bool):
        """Handle updates from /user_inside topic."""
        self.user_inside = bool(msg.data)
        self.evaluate_logic()

    def auth_callback(self, msg: Bool):
        """Handle updates from /authorization_result topic."""
        self.authorization_result = bool(msg.data)
        self.evaluate_logic()

    # ==========================================================
    # CORE LOGIC
    # ==========================================================
    def evaluate_logic(self):  # pylint: disable=too-many-return-statements
        """Evaluate door control logic based on current system state."""
        if self.state is None:
            return

        now_sec = self.get_clock().now().nanoseconds * 1e-9

        # -------------------------
        # STATE 2: BOARDING
        # -------------------------
        if self.state == 2:
            if not self.user_inside and self.authorization_result:
                self.publish_door(True)
                return

            self.publish_door(False)
            return

        # -------------------------
        # STATE 3: DROPOFF
        # -------------------------
        if self.state == 3:
            if self.door_open_time is None and not self.state3_expired:
                self.door_open_time = now_sec
                self.publish_door(True)
                return

            if self.state3_expired:
                self.publish_door(False)
                return

            elapsed = now_sec - self.door_open_time

            if elapsed >= 120.0:
                self.publish_door(False)
                self.state3_expired = True
                self.door_open_time = None
                return

            self.publish_door(True)
            return

        # -------------------------
        # OTHER STATES
        # -------------------------
        if self.door_open_time is not None or self.state3_expired:
            self.door_open_time = None
            self.state3_expired = False
            self.publish_door(False)

    # ==========================================================
    # HELPERS
    # ==========================================================
    def publish_door(self, status: bool):
        """Publish door status if it has changed."""
        self.current_status = bool(status)

        if self.last_published == self.current_status:
            return

        msg = Bool()
        msg.data = self.current_status
        self.door_pub.publish(msg)
        self.last_published = self.current_status

    def timer_callback(self):
        """Continuously publish current door status."""
        msg = Bool()
        msg.data = self.current_status
        self.door_pub.publish(msg)


def main(args=None):  # pragma: no cover
    """Main entry point."""
    rclpy.init(args=args)
    node = DoorOperationControl()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:  # pragma: no cover
        node.get_logger().info("Shutting down door_operation_control")
    finally:  # pragma: no cover
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
