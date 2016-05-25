#!/usr/bin/env python
#import roslib;roslib.load_manifest(PKG)
import cv_bridge
import cv2.cv as cv
import cv2
import sys
import os
import rospy
import baxter_interface
from std_msgs.msg import String, Header
from sensor_msgs.msg import Image
import argparse
import numpy as np
from grasp.msg import vec
from geometry_msgs.msg import (
    PoseStamped,
    Pose,
    Point,
    Quaternion,
)
from baxter_core_msgs.srv import (
    SolvePositionIK,
    SolvePositionIKRequest,
)
#import roslib
#roslib.load_manifest('my package')

from sensor_msgs.msg import (
    Image,
)
from std_msgs.msg import (
    UInt16,
)
from rospy.numpy_msg import numpy_msg

vx = 0
xy = 0

def sendVec(vec):
	a=1

def stream(camera_topic):
	global vx,vy
	rate = rospy.Rate(100)
	imageSub = rospy.Subscriber(camera_topic, Image, callback)
	#vecPub.publish(np.array((vx,vy))
	#print vx
	print("Displaying. Press Ctrl-C to stop...")
	while not rospy.is_shutdown():
		rate.sleep()
		
def callback(data):
	faceDetect(data)

def callVec(data):
	sendVec(data)
			
def faceDetect(data):

	global vx,vy
	bridge = cv_bridge.CvBridge()
	try:
		cv_image = bridge.imgmsg_to_cv2(data,desired_encoding='bgr8')
	except cv_bridge.CvBridgeError, e:
		print e
		
	(rows, cols, channels) = cv_image.shape
	#turn image grey for processing
	grey = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
	#create haar cascade
	cascPath = '/home/birl/ros_ws/src/grasp/scripts/haarcascade_frontalface_default.xml'
	faceCas = cv2.CascadeClassifier(cascPath)
	#print faceCas.empty()
	#detect faces
	sf=1.2
	faces=faceCas.detectMultiScale(grey,scaleFactor=sf,minNeighbors=8,minSize=(30,30),flags=cv2.cv.CV_HAAR_SCALE_IMAGE)
	if len(faces) > 0:
		print "Found {0} faces...".format(len(faces))
	#else:
		#print 'Found no faces!'

	vecPub = rospy.Publisher('vec', numpy_msg(vec), queue_size=10)
	if len(faces) > 0:
		cx = faces[0,0] + 0.5*faces[0,2]
		cy = faces[0,1] + 0.5*faces[0,3]
	 	vx = cx - 640
		vy = cy - 400
		print vy, vx
		
	else:
		vx = 0
		vy = 0
	vecPub.publish(np.array((vx,vy)))
	#print vx
	for (x,y,w,h) in faces:
		cv2.rectangle(cv_image, (x,y),(x+w, y+h), (0, 255, 0), 2)		
	# display image
	cv2.imshow("Face detect", cv_image)
	cv2.waitKey(2)

def main(args):
	rospy.init_node('imgConv', anonymous=True)
	#limb = baxter_interface.Limb('left')
	res = (1280,800)
	# define cams
	leftCam = baxter_interface.CameraController("left_hand_camera")
	rightCam = baxter_interface.CameraController("right_hand_camera")
	#headCam = baxter_interface.CameraController("head_camera")
	#define argument for command line
	arg_fmt = argparse.RawDescriptionHelpFormatter
	parser = argparse.ArgumentParser(formatter_class=arg_fmt,description=main.__doc__)
	parser.add_argument('-c', '--camera', choices=['left', 'right', 'head'], required=True,help="the camera to display")
	args = parser.parse_args(rospy.myargv()[1:])
	# define camera
	if(args.camera == 'left'):
		leftCam.open()
		leftCam.resolution = res
		camera_topic = '/cameras/left_hand_camera/image'
	if(args.camera == 'right'):
		rightCam.resolution = res
		rightCam.open()
		camera_topic = '/cameras/right_hand_camera/image'
	#if(args.camera == 'head'):
	#	headCam.resolution = res
	#	headCam.open()
	#	camera_topic = '/cameras/head_camera/image'
	
	
	stream(camera_topic)
	#pose = limb.endpoint_pose()
	#x,y,z = pose['position']
	#print x,y,z
	
	print 'Closed'
	cv2.destroyAllWindows()
	return 0
	
if __name__ == '__main__':
	main(sys.argv)
		
		
