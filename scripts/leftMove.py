#!/usr/bin/env python

import rospy
import baxter_interface

rospy.init_node('Hello_baxter')
rospy.loginfo("Started...")
limb = baxter_interface.Limb('left')

point1 = {'left_s0': 0.007,'left_s1': -0.187,'left_e0': -1.42,'left_e1': 1.797,'left_w0': 0.2,'left_w1': 0.314,'left_w2': -0.663}

point2 = {'left_s0': 0.162,'left_s1': -0.20,'left_e0': -1.63,'left_e1': 1.35,'left_w0': 0.787,'left_w1': 0.227,'left_w2': 0.653}


limb.move_to_joint_positions(point1)
limb.move_to_joint_positions(point2)

quit()
