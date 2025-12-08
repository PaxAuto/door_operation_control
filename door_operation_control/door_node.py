#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, Bool


class DoorOperationControl(Node):
    def __init__(self):
        super().__init__("door_operation_control")

        # SUBSCRIBER
        self.state_sub = self.create_subscription(Int32, "/state", self.state_callback, 10)
        self.user_inside_sub = self.create_subscription(Bool, "/user_inside", self.user_inside_callback, 10)
        self.auth_sub = self.create_subscription(Bool, "/authorization_result", self.auth_callback, 10)

        # PUBLISHER
        self.door_pub = self.create_publisher(Bool, "/door_status", 10)

        # internal state
        self.state = None
        self.user_inside = False
        self.authorization_result = False
        self.door_open_time = None  
        self.state3_expired = False  
        self.last_published = None  
        self.current_status = False  

        # timer to publish /door_status continuously (1 Hz)
        self.timer = self.create_timer(1.0, self.timer_callback)

        self.get_logger().info("✅ Door Operation Control Node started and ready!")


    def state_callback(self, msg: Int32):
        prev = getattr(self, "state", None)
        try:
            self.state = int(msg.data)
        except Exception:
            self.get_logger().warning(f"Ignoring non-int /state payload: {msg.data}")
            return

        # Evaluate immediately on state change
        self.evaluate_logic()

    def user_inside_callback(self, msg: Bool):
        prev = self.user_inside
        self.user_inside = bool(msg.data)
       
        self.evaluate_logic()

    def auth_callback(self, msg: Bool):
        prev = self.authorization_result
        self.authorization_result = bool(msg.data)
        self.evaluate_logic()

    
    def evaluate_logic(self):
        # Wait until /state received at least once
        if self.state is None:
            # not ready until we have a state
            return

    
        now_sec = self.get_clock().now().nanoseconds * 1e-9

        # ============================================================
        # USER STORY 4.3 — BOARDING (state = 2)
        # ============================================================
        if self.state == 2:
            # open only if user is OUTSIDE AND authorized
            if (not self.user_inside) and self.authorization_result:
                self.publish_door(True)
                return

            # CLOSE door when user_inside True
            if self.user_inside:
                self.publish_door(False)
                return

            # state==2 but not authorized or other -> keep closed
            self.publish_door(False)
            return

        # ============================================================
        # USER STORY 7.3 — DROPOFF & DEBOARDING (state = 3)
        # ============================================================
        elif self.state == 3:
            if self.door_open_time is None and not self.state3_expired:
                self.door_open_time = now_sec
                self.publish_door(True)
                return

       
            if self.state3_expired:
                self.publish_door(False)
                return

            elapsed = now_sec - self.door_open_time

            # After 120 seconds, set door closed 
            if elapsed >= 120.0:
                self.publish_door(False)
                
                self.state3_expired = True
                self.door_open_time = None
                return

         
            self.publish_door(True)
            return

      
        else:
            # reset timer and expired flag when leaving state 3
            if self.door_open_time is not None or self.state3_expired:
               self.door_open_time = None
               self.state3_expired = False
               self.publish_door(False)
            return

    # -------------------------------------------------
    # HELPER
    # -------------------------------------------------
    def publish_door(self, status: bool):
        """
        Update current_status and publish immediately if it changed since last immediate publish.
        Continuous publishing is handled by the timer_callback which always publishes current_status.
        """
        # update stored state for continuous publishing
        self.current_status = bool(status)

       
        if self.last_published is not None and self.last_published == self.current_status:
            return

        msg = Bool()
        msg.data = self.current_status
        self.door_pub.publish(msg)
        self.last_published = self.current_status
       

    def timer_callback(self):
        """Continuously publish the current door status at fixed rate."""
        msg = Bool()
        msg.data = self.current_status
        self.door_pub.publish(msg)
      

def main(args=None):
    rclpy.init(args=args)
    node = DoorOperationControl()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down door_operation_control (KeyboardInterrupt)")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
