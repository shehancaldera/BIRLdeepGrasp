#!/usr/bin/env python
import sys
import rospy
import moveit_commander
import moveit_msgs.msg
import geometry_msgs.msg

moveit_commander.roscpp_initialize(sys.argv)
rospy.init_node('ikfast', anonymous=True)
robot = moveit_commander.RobotCommander()
group = moveit_commander.MoveGroupCommander("left_arm")

print group.get_planning_frame()
print group.get_end_effector_link()
print robot.get_group_names
print robot.get_current_state()

pose_target = geometry_msgs.msg.Pose()
pose_target.orienation.w = 1.0
pose_target.position.x = 0.7
pose_target.position.y = -0.05
pose_target.position.z = 1.1
group.set_pose_target(post_target)

plan1 = group.plan()
group.go(wait=True)
