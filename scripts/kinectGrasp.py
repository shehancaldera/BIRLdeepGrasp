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
from baxter_pykdl import baxter_kinematics

from baxter_core_msgs.srv import (
    SolvePositionIK,
    SolvePositionIKRequest,
)
import copy
import moveit_commander
import moveit_msgs.msg
import geometry_msgs.msg



class baxterGrasp():
	def __init__(self,arm):
		# Define arm
		self.limb        = baxter_interface.Limb(arm)
		# Define cameras
		#self.resetCameras()
		#self.closeCameras()
		self.armCam = baxter_interface.CameraController('left_hand_camera')
		self.armCam.resolution = (int(640),int(400))
		self.armCam.open()
		self.filmCam = baxter_interface.CameraController('right_hand_camera')
		self.filmCam.resolution = (int(640),int(400))
		self.filmCam.open()
		# Define Gripper
		self.wristAngle  = arm + '_w2'
		self.grip        = baxter_interface.Gripper(arm)
		self.grip.calibrate()
		self.grip.set_holding_force(40)
		# Topics
		self.kinectTopic = '/transformedPointCloud'
		self.camTopic    = '/cameras/left_hand_camera/image'
		self.filmTopic   = '/cameras/right_hand_camera/image'
		self.viewTopic   = '/view'
		self.viewImage   = None
		self.handImage   = None
		self.filmImage   = None
		self.feat        = None
		self.featStatic  = None
		self.featTopic   = '/feature'
		self.bridge = cv_bridge.CvBridge()
		# Image
		self.display = np.zeros((880,640+480,3), dtype = "uint8")
		# Inverse kinematics
		#self.IK          = baxter_kinematics(arm)
		#self.robot = moveit_commander.RobotCommander()
		#self.scene = moveit_commander.PlanningSceneInterface()
		#self.IKlimb = moveit_commander.MoveGroupCommander(arm+"_arm")
		# Poses
		# seed orientation pose 
		#self.a = -0.207902243738
		#self.b = 0.977069770132
		#self.c = -0.0233761695371
		#self.d = 0.0395585141385
		# move locations
		self.start = {'left_w0': -0.220893233203125, 'left_w1': 1.7115390621276856, 'left_w2': 3.0564567163696292, 'left_e0': 0.22166022359619142, 'left_e1': 0.6074563913085937, 'left_s0': -0.33402431618041994, 'left_s1': -0.794602047216797}
		self.mid = {'left_w0': -0.645422415765381, 'left_w1': 1.6854613887634278, 'left_w2': 3.0549227355834963, 'left_e0': -0.1219514724975586, 'left_e1': 0.5104321065856934, 'left_s0': -0.7907670952514649, 'left_s1': -0.9031311878356935}
		self.box = {'left_w0': 1.010126347668457, 'left_w1': 1.6409759459655764, 'left_w2': 3.039582927722168, 'left_e0': -1.7257283843994142, 'left_e1': 2.0739420228515626, 'left_s0': -0.5729418236206055, 'left_s1': -0.37544179740600586}
		#self.seed = {'left_w0': -0.10814564542236328, 'left_w1': 1.2808739564208986, 'left_w2': 0.26039323844604495, 'left_e0': -0.0019174759826660157, 'left_e1': 0.6166602760253906, 'left_s0': -0.9871166358764649, 'left_s1': -0.4475388943542481}
		self.seed = np.array([ 0.87380432,  0.08285656,  0.15036509,  0.2033632 ,  0.97567312,-0.05176495,  0.06344892])
		# ROS stuff
		self.rate        = rospy.Rate(60)
		self.z0          = 0.2
		# start correct
		self.limb.move_to_joint_positions(self.start)
		# progress Flags
		self.gotGrasp = 0
		self.gotLoc   = 0
		self.gotFeat  = 0
		self.featLoc  = (0,0)
		self.still    = 0
	 	cv2.namedWindow('handImage')

	def camCallback(self,data):
		self.camData(data)
	
	def camData(self,data):
		# print "cam callback"
		try:
			self.handImage = self.bridge.imgmsg_to_cv2(data,desired_encoding='bgr8')
			if self.handImage is not None:
				cv2.circle(self.handImage,((360,100)),3,(0,255,0),2)
				cv2.circle(self.handImage,self.featLoc,3,(255,0,0),2)
				self.display[-400:,:640,:] = self.handImage
				if self.filmImage is not None:
					self.display[-400:,-480:,:] = self.filmImage[:,-580:-100:]
				cv2.imshow('handImage',self.display)
				cv2.waitKey(1)
		except cv_bridge.CvBridgeError, e:
			print e
	
		return 0

	def filmCallback(self,data):
		#print "film callback"
		self.filmData(data)
	
	def filmData(self,data):
		# print "film callback"
		try:
			self.filmImage = self.bridge.imgmsg_to_cv2(data,desired_encoding='bgr8')
		except cv_bridge.CvBridgeError, e:
			print e

		return 0

	def viewCallback(self,data):
		#print "view callback"
		self.viewData(data)
		return 0
	
	def viewData(self,data):
		# print "view callback"
		try:
			self.viewImage = self.bridge.imgmsg_to_cv2(data,desired_encoding='bgr8')
			self.display[0:480,-(640+480):,:] = self.viewImage
		except cv_bridge.CvBridgeError, e:
			print e

		return 0

	def featCallback(self,data):
		self.featData(data)
		return 0
	
	def featData(self,data):
		# print "feat callback"
		try:
			self.feat = self.bridge.imgmsg_to_cv2(data,desired_encoding='bgr8')
			self.gotFeat = 1
			large =  cv2.resize(self.feat,(0,0),fx=5, fy=5, interpolation = cv2.INTER_CUBIC)
			cv2.imshow('feature',large)
			cv2.waitKey(1)
			# cancel thread once found for speed
			self.fsub.unregister()
			return 0
		except cv_bridge.CvBridgeError, e:
			print e
		return 0
	
	def kinectCallback(self,data):
		self.kinectData(data)
		return 0

	def kinectData(self,data):
		print "Finding world coordinates"
		print self.gotGrasp, self.gotLoc
		if(self.gotGrasp and self.gotFeat):
			self.generator = pc2.read_points(data, field_names = None, skip_nans=False, uvs=[[self.u,self.v]])
			worldCoord     = next(self.generator)
			self.x         = worldCoord[0]+0.00#-0.03
			self.y         = worldCoord[1]-0.07
			self.z         = np.max((worldCoord[2]-0.02,-0.030))
			self.gotLoc    = 1
			print "World Coordinates"
			print self.x,self.y,self.z
			if self.gotFeat:
				self.startGrasp()
				self.ksub.unregister()
			
		else:
			print "Need grasp or feat"
			print self.gotGrasp, self.gotFeat
		print "HERE4"
		return 0
		
	def graspCallback(self,data):
		self.graspData(data)
		print "HERE10"
		return 0
	
	def graspData(self,data):
		if(not self.gotGrasp):
			print "Finding grasp parameters..."
			print self.gotGrasp, self.gotLoc
			# u,v,theta
			self.u     = int(data.data[0])
			self.v     = int(data.data[1])
			# no minus?			
			self.theta = data.data[2]
			print "THETA"
			print self.theta
			if self.theta < 0:
				self.theta = np.pi + self.theta
			print "THETA"
			print self.theta
			self.gotGrasp = 1
			print "Grasp parameters"
			print self.u,self.v,self.theta
			self.grasp()
			print "grasping done"
			return 0

	def stream(self):
		rate = rospy.Rate(10)
		print "Initialize grasp"
		# get film cam
		rospy.Subscriber(self.filmTopic, Image, self.filmCallback)
		# get handcam
		rospy.Subscriber(self.camTopic, Image, self.camCallback)
		# get view
		rospy.Subscriber(self.viewTopic, Image, self.viewCallback)
		# Get grasping coordinates
		self.gsub = rospy.Subscriber("vec", numpy_msg(vec), self.graspCallback)
		print("Starting grasp procedure. Press Ctrl-C to stop...")
		rospy.spin()
		while not rospy.is_shutdown():
			rate.sleep()
	
	def setTheta(self):
		print "setting theta"
		print self.theta
		phi = np.pi + np.random.normal(0,0.02,1)
		# don't divide by 2?
		alpha = self.theta/2 + np.random.normal(0,0.0003,1)
		a = np.cos(alpha)
		b = np.sin(alpha)
		c = np.abs(np.random.normal(0,0.02,1))
		q = np.array([a,b,c])
		a, b, c = q/np.linalg.norm(q) * np.sin(phi/2)
		d = np.cos(phi/2)
		self.a = a
		self.b = b
		self.c = c
		self.d = d
		#return a,b,c,d
	
	def grasp(self): 
		go = raw_input('Initiate grasp?')
		self.graspInit()
		print "AM I HERE?"
	
	def graspInit(self):
		# Get feature
		self.fsub = rospy.Subscriber(self.featTopic, Image, self.featCallback)
		# Get transformed Pointcloud
		self.ksub = rospy.Subscriber(self.kinectTopic, PointCloud2, self.kinectCallback)
		print "HERE"
		return 0
		#self.startGrasp()
		#rospy.spin()
		#self.startGrasp()
		#while not rospy.is_shutdown():
		#	print "HERE3"
		#	rate.sleep()
	
	
	def startGrasp(self):
		print "start grasping again"
		# save feature before arm gets in the way
		self.featStatic = np.copy(self.feat)
		#rospy.sleep(2.0)
		#self.setTheta()
		ikSearch = 1
		x = self.x
		y = self.y
		z = self.z0
		self.setTheta()
		while(ikSearch):
			print ikSearch
			ikSearch = self.ikSolver(x,y,z,self.a,self.b,self.c,self.d)
			if(ikSearch):
				# Position
				x = self.x  + np.random.normal(0,0.01,1)
				y = self.y  + np.random.normal(0,0.01,1)
				z = self.z0 + np.random.normal(0,0.01,1)
				# Orientations
				self.setTheta()
				print "x,y,z,a,b,c,d"
				print x,y,z,self.a,self.b,self.c,self.d

		print "Valid and desired grasping coords"
		print "x,y,z,a,b,c,d"
		print x,y,z,self.a,self.b,self.c,self.d
		print "theta, new theta"
		print self.theta, np.arcsin(np.sqrt(1+self.c**2)*self.a/np.sqrt(1-self.d**2))*2
		print self.x,self.y,self.z0,self.a,self.b,self.c,self.d
		self.startPose = self.limb.joint_angles()
		rospy.sleep(0.5)
		self.visualServo()
		#self.endGrasp()

	def ikSolver(self,x,y,z,a,b,c,d):
		rpy_pose = (x,y,z,a,b,c,d)
		quaternion_pose = conversions.list_to_pose_stamped(rpy_pose, "base")
       		node = "ExternalTools/left/PositionKinematicsNode/IKService"
        	ik_service = rospy.ServiceProxy(node, SolvePositionIK)
       		ik_request = SolvePositionIKRequest()
       		hdr = Header(stamp=rospy.Time.now(), frame_id="base")
      		ik_request.pose_stamp.append(quaternion_pose)
       		try:
            		rospy.wait_for_service(node, 10.0)
                	ik_response = ik_service(ik_request)
			if ik_response.isValid[0]:
            			print("Valid joint configuration found")
            			# convert response to joint position control dictionary
            			limb_joints = dict(zip(ik_response.joints[0].name, ik_response.joints[0].position))
            			# move limb
            			self.limb.move_to_joint_positions(limb_joints)
				rospy.sleep(1)
				self.setTheta()	
				rospy.sleep(1)
				return 0
			else:
				print "Failed"
				return 1
       	        except (rospy.ServiceException, rospy.ROSException), error_message:
            		rospy.logerr("Service request failed: %r" % (error_message,))
            		sys.exit("ERROR - baxter_ik_move - Failed to append pose")


	def visualServo(self):
		print "Starting visual Servo"
		if self.featStatic is not None and self.handImage is not None:
			#error = 1
			ikSearch = 1
			while(ikSearch):
				print "in visual sevoing loop"
				res = cv2.matchTemplate(self.handImage,self.featStatic,cv2.TM_CCORR)
				cv2.imshow('res',res)
				cv2.waitKey(1)
				_,_,_,loc = cv2.minMaxLoc(res)
				dx = loc[1] + 15
				dy = loc[0] + 15
				ey = 360 - dy
				ex = 100 - dx 
				print ex,ey
				if (np.absolute(ex)<50 and np.absolute(ey)<50):
					print "breaking"
					break
				# redefining loc
				self.featLoc = (dy,dx)
				# add 5,5
				# define centre of gripper in px
				# find px translation
				# add scale factor and do IK loop till error = 0
				rospy.sleep(5.0)
				k = 0.0003
				# proportional feedback
				x0 = self.x + k*(ex*np.cos(self.theta) + ey*np.sin(self.theta))
				y0 = self.y + k*(-ex*np.sin(self.theta) + ey*np.cos(self.theta))
				x = x0
				y = y0
				z = self.z0
				while(ikSearch):
					print self.x, self.y
					print x0, y0
					print ex,ey
					print ikSearch
					ikSearch = self.ikSolver(x,y,z,self.a,self.b,self.c,self.d)
					count = 0
					over = 1
					if(ikSearch and over):
						x = x0      + np.random.normal(0,0.005,1)
						y = y0      + np.random.normal(0,0.005,1)
						z = self.z0 + np.random.normal(0,0.005,1)
						# Orientations
						self.setTheta()
						count = count + 1
						if (count>50):
							over = 0
							break
					print x,y,z,self.a,self.b,self.c,self.d
				print "pausing while moving"
				rospy.sleep(1.0)
			self.endGrasp()
		else: 
			print self.gotFeat
			print "waiting for images, going for it"
			self.endGrasp()
		

	def endGrasp(self):
		print "looking for place location"
		#rospy.sleep(2.0)
		ikSearch = 1
		x = self.x
		y = self.y
		z = self.z
		self.setTheta()
		while(ikSearch):
			ikSearch = self.ikSolver(x,y,z,self.a,self.b,self.c,self.d)
			if(ikSearch):
				#x = self.x  + np.random.normal(0,0.01,1)
				#y = self.y  + np.random.normal(0,0.01,1)
				#z = self.z0 + np.random.normal(0,0.01,1)
				self.setTheta()
				print x,y,z,self.a,self.b,self.c,self.d	
		print "placing"
		print x,y,z,self.a,self.b,self.c,self.d
		print self.x,self.y,self.z,self.a,self.b,self.c,self.d
		self.place()
			
	
	
	
	def place(self):
		print 'Gripping'
		self.grip.close()
		rospy.sleep(1)
		self.limb.move_to_joint_positions(self.startPose)
		rospy.sleep(1)
		self.limb.move_to_joint_positions(self.mid)
		rospy.sleep(1)
		self.limb.move_to_joint_positions(self.box)
		print 'Dropping'
		rospy.sleep(2.0)
		self.grip.open()
	    	rospy.sleep(2.0)
		self.restart()
		
	def restart(self):
		self.limb.move_to_joint_positions(self.start)
		print 'Grasp Complete'
		self.gotGrasp = 0
		self.gotLoc   = 0
		self.gotFeat   = 0

def main(args):
	# Initialize ROS Node
	#moveit_commander.roscpp_initialize(sys.argv)
	rospy.init_node('kinect_view',anonymous = True)
	baxter = baxterGrasp('left')
	baxter.stream()
	return 0	

if __name__ == '__main__':
	main(sys.argv)
