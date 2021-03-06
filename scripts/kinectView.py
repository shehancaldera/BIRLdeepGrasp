#!/usr/bin/env python
import sys
import baxter_interface
from std_msgs.msg import String, Header
from geometry_msgs.msg import (
    PoseStamped,
    Pose,
    Point,
    Quaternion,
)
import os
import tf
import tf2_ros
from tf2_sensor_msgs.tf2_sensor_msgs import do_transform_cloud
import cv_bridge
import cv2.cv as cv
import cv2
import rospy
import numpy as np
import numpy.matlib
from sensor_msgs.msg import Image
import sensor_msgs.point_cloud2 as pc2
from geometry_msgs.msg import Point
from sensor_msgs.msg import PointCloud2
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import threading
import matplotlib.animation as animation
import ctypes
import struct
from grasp.msg import vec
from rospy.numpy_msg import numpy_msg
from moveit_commander import conversions

from baxter_core_msgs.srv import (
    SolvePositionIK,
    SolvePositionIKRequest,
)

graspPoint = np.zeros((3,1))
cloudy = np.zeros((480*640,4))
save=1;
kinectRotation = tf.transformations.euler_matrix(0.01,-0.5,0.01)[0:3,0:3]
#kinectRotation = np.linalg.inv(kinectRotation)
kinectTranslation = np.transpose(np.matrix([[0.32,0.05,-0.91]]))
#kinectTransformation = np.ones((4,4))
#kinectTransformation[0:3,0:3] = rotation
#kinectTransformation[0:3,3] = rotation



#fig = plt.figure(figsize=(12,8))
#ax = fig.add_subplot(111,projection='3d')

def stream(kinectTopic):
	rate = rospy.Rate(10)
	depthSub = rospy.Subscriber(kinectTopic, PointCloud2, callback)
	rospy.Subscriber("vec", numpy_msg(vec), callbackVec)
	print("Starting grasp procedure. Press Ctrl-C to stop...")
	while not rospy.is_shutdown():
		rate.sleep()

def callbackVec(data):
        global graspPoint
	graspPoint = np.matrix([[data.data[0],data.data[1],data.data[2]]])
			

def callback(data):
	streamDisp(data)

def streamDisp(data):
	print 'size of data: ', sys.getsizeof(data)
        global cloudy,ax,fig,graspPoint,save,kinectRotation,kinectTranslation,Trans
	#data = do_transform_cloud(data,Trans)
	left = baxter_interface.Limb('left')
	grip = baxter_interface.Gripper('left')
	if(not grip.calibrated()):
	    	go = raw_input('grip cal?')
		grip.calibrate()
		grip.set_holding_force(40)
	#print dir(data)
	#print data.fields
	#a = []
 	#qq = data.deserialize_numpy(data.data,cloudy)
	#print type(cloudy)
	#print type(qq)
	#print qq.size


	go = raw_input('find?')
	print 'grasp parameters', graspPoint

	x = graspPoint[0,0]
	y = graspPoint[0,1]
	theta = graspPoint[0,2]
	x = int(x)
	y = int(y)


	gen2 = pc2.read_points(data, field_names = None, skip_nans=False, uvs=[[x,y]])
	#print type(gen2)
	in_data2 = next(gen2)
	print'in data', in_data2
	graspWorld = np.matrix([[in_data2[0]],[in_data2[1]],[in_data2[2]]])
	#reflect = np.matrix([[0,1,0],[1,0,0],[0,0,1]])
	#kinectRotation = np.dot(reflect,kinectRotation)
	graspPointTorso = np.dot(kinectRotation,graspWorld)
	graspPointTorso = np.add(graspPointTorso,kinectTranslation)
	#graspPointTorso = np.add(graspWorld,kinectTranslation)
	graspPointTorso = graspWorld
	#print 'pointTorso',graspPointTorso[0],graspPointTorso[1],graspPointTorso[2]
	#print 'rotated', np.dot(kinectRotation,graspWorld)
	angles = left.joint_angles()
	angles['left_w2'] = theta
	left.move_to_joint_positions(angles)
	pose = left.endpoint_pose()
	xw,yw,zw = pose['position']
	a,b,c,d =  pose['orientation']
	#print 'position',xw,yw,zw
	#print 'orientation',a,b,c,d
	#rpy_pose = (0.7*in_data[1]+0.6, 0.7*in_data[0]+0.06, in_data[2]-1.0, a,b,c,d)
	rpy_pose = (graspPointTorso[0]-0.02, graspPointTorso[1]-0.07, graspPointTorso[2]+0.25, a,b,c,d)
	#prePick = left.joint_angles()
	print 'pose',rpy_pose
	go = raw_input('move?')
	quaternion_pose = conversions.list_to_pose_stamped(rpy_pose, "base")

        node = "ExternalTools/" + 'left'+ "/PositionKinematicsNode/IKService"
        ik_service = rospy.ServiceProxy(node, SolvePositionIK)
        ik_request = SolvePositionIKRequest()
        hdr = Header(stamp=rospy.Time.now(), frame_id="base")

        ik_request.pose_stamp.append(quaternion_pose)
        try:
            rospy.wait_for_service(node, 5.0)
            ik_response = ik_service(ik_request)
        except (rospy.ServiceException, rospy.ROSException), error_message:
            rospy.logerr("Service request failed: %r" % (error_message,))
            sys.exit("ERROR - baxter_ik_move - Failed to append pose")
	    print 'trying new angle'
	    angles['left_w1'] = 1.2;
	    leftLimb.move_to_joint_positions(angles)
	    xw,yw,zw = pose['position']
	    a,b,c,d =  pose['orientation']
	    rpy_pose = (graspPointTorso[0]-0.00, graspPointTorso[1]-0.07, graspPointTorso[2]+0.25, a,b,c,d)
	    quaternion_pose = conversions.list_to_pose_stamped(rpy_pose, "base")
            ik_request.pose_stamp.append(quaternion_pose)
	    try:
            	rospy.wait_for_service(node, 5.0)
            	ik_response = ik_service(ik_request)
            except (rospy.ServiceException, rospy.ROSException), error_message:
            	rospy.logerr("Service request failed: %r" % (error_message,))
            	sys.exit("ERROR - baxter_ik_move - Failed to append pose")

        if ik_response.isValid[0]:
            print("PASS: Valid joint configuration found")
            # convert response to joint position control dictionary
            limb_joints = dict(zip(ik_response.joints[0].name, ik_response.joints[0].position))
            # move limb
            left.move_to_joint_positions(limb_joints)

        else:
            # display invalid move message on head display
            #self.splash_screen("Invalid", "move")
            # little point in continuing so exit with error message
	    print 'failed'
            print "requested move =", rpy_pose
            sys.exit("ERROR - baxter_ik_move - No valid joint configuration found")
        preDropAngles = left.joint_angles()
	#go = raw_input('grasp?')
	rpy_pose = (graspPointTorso[0]-0.03, graspPointTorso[1]-0.09, np.max((graspPointTorso[2]+0.1,0.06)), a,b,c,d) #0.06
	print rpy_pose
	quaternion_pose = conversions.list_to_pose_stamped(rpy_pose, "base")

        node = "ExternalTools/" + 'left'+ "/PositionKinematicsNode/IKService"
        ik_service = rospy.ServiceProxy(node, SolvePositionIK)
        ik_request = SolvePositionIKRequest()
        hdr = Header(stamp=rospy.Time.now(), frame_id="base")

        ik_request.pose_stamp.append(quaternion_pose)
        try:
            rospy.wait_for_service(node, 5.0)
            ik_response = ik_service(ik_request)
        except (rospy.ServiceException, rospy.ROSException), error_message:
            rospy.logerr("Service request failed: %r" % (error_message,))
            sys.exit("ERROR - baxter_ik_move - Failed to append pose")

        if ik_response.isValid[0]:
            print("PASS: Valid joint configuration found")
            # convert response to joint position control dictionary
            limb_joints = dict(zip(ik_response.joints[0].name, ik_response.joints[0].position))
            # move limb
            left.move_to_joint_positions(limb_joints)
	    
	    go = raw_input('grip?')
            grip.close()
	    rospy.sleep(2.0)
	    left.move_to_joint_positions(preDropAngles)
	    #go = raw_input('go back?')
	    box0 = {'left_w0': -0.645422415765381, 'left_w1': 1.6854613887634278, 'left_w2': 3.0549227355834963, 'left_e0': -0.1219514724975586, 'left_e1': 0.5104321065856934, 'left_s0': -0.7907670952514649, 'left_s1': -0.9031311878356935}
	    #box0 = {'left_w0': 1.223349676940918, 'left_w1': 1.5362817573120118, 'left_w2': 3.0399664229187016, 'left_e0': -1.6781749800292969, 'left_e1': 1.530912824560547, 'left_s0': -0.3900146148742676, 'left_s1': -0.4245291825622559}
	    left.move_to_joint_positions(box0)
	    box = {'left_w0': 1.010126347668457, 'left_w1': 1.6409759459655764, 'left_w2': 3.039582927722168, 'left_e0': -1.7257283843994142, 'left_e1': 2.0739420228515626, 'left_s0': -0.5729418236206055, 'left_s1': -0.37544179740600586}
	    left.move_to_joint_positions(box)
	    grip.open()
	    rospy.sleep(2.0)
	    leftPoint = {'left_w0': -0.220893233203125, 'left_w1': 1.7115390621276856, 'left_w2': 3.0564567163696292, 'left_e0': 0.22166022359619142, 'left_e1': 0.6074563913085937, 'left_s0': -0.33402431618041994, 'left_s1': -0.794602047216797}
            left.move_to_joint_positions(leftPoint)
	    


        else:
            # display invalid move message on head display
            #self.splash_screen("Invalid", "move")
            # little point in continuing so exit with error message
	    print 'failed'
            print "requested move =", rpy_pose
            sys.exit("ERROR - baxter_ik_move - No valid joint configuration found")
	


def main(args):
        global cloudy,ax,fig,Trans
	rospy.init_node('kinect_view')
	#kinectTopic = '/camera/depth/points'
	#kinectTopic = '/camera/depth_registered/points'
        kinectTopic = '/transformedPointCloud'
	tfBuffer = tf2_ros.Buffer()
	listener = tf2_ros.TransformListener(tfBuffer)
	try:
		Trans = tfBuffer.lookup_transform('torso','camera_link',rospy.Time(0), timeout = rospy.Duration(5))
		
		stream(kinectTopic)
	except(tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException),error:
		print 'Fail: ',error
	
	return 0	

	#save=0
	#if(save):
		
	#	height = data.height
	#	width = data.width
	#	cloudy = np.zeros((height*width,6))
	#	#cloudyCol = np.zeros((height,width,3), dtype=np.uint8)
	#	gen = pc2.read_points(data, skip_nans=True)
	#	print next(gen)
	#	print 'loading'
	#	print type(data)
	#	print 'width ',width, ' height ',height
	#	buffer = list(gen)
	#	print 'size of buffer', len(buffer)
	#	count=0
	#	for x in buffer:
	#		#print type(x)
	#		#print x
##
	#		cloudy[count,0:3] = np.asarray(x[0:3])
	#		s = struct.pack('>f', x[3])
	#		i = struct.unpack('>l',s)[0]
	#		pack = ctypes.c_uint32(i).value
	#		r = (pack & 0x00FF0000)>>16
	#		g = (pack & 0x0000FF00)>>8
	#		b = (pack & 0x000000FF)
	#		
	#		cloudy[count,3:6] = np.array([[r/255.0,g/255.0,b/255.0]])
	#		#print 'rgb:',r,g,b
	#		count=count+1	
	#	np.save('cloudy',cloudy)
	#	np.save('graspPoint',graspPoint)
	#	save = 0
	#	print 'count ',count

if __name__ == '__main__':
	main(sys.argv)
