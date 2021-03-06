#!/usr/bin/env python

import rospy
import baxter_interface

rospy.init_node('ArmInit')
rospy.loginfo("Started...")
leftLimb = baxter_interface.Limb('left')
rightLimb = baxter_interface.Limb('right')

leftPoint = {'left_s0': 0.5989,'left_s1': 0.213,'left_e0': -2.294,'left_e1': 1.868,'left_w0': -2.11,'left_w1': -1.4734,'left_w2': 3.289}
rightPoint = {'right_s0': -0.7497331092224122, 'right_s1': -0.14227671791381838, 'right_w0': 2.49501974864502, 'right_w1': -1.0657331511657715, 'right_w2': 2.489, 'right_e0': 1.974616766949463, 'right_e1': 1.8411604385559084}


leftLimb.move_to_joint_positions(leftPoint)
rightLimb.move_to_joint_positions(rightPoint)

quit()
