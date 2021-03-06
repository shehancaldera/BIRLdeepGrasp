#!/usr/bin/env python
import cv_bridge
import cv2.cv as cv
import cv2
import sys
import os
import rospy
import baxter_interface
from std_msgs.msg import String, Header
from sensor_msgs.msg import Image
from stereo_msgs.msg import DisparityImage
import argparse
import numpy as np
os.environ['GLOG_minloglevel'] = '2'
import caffe
caffe.set_mode_cpu()
import math
from rospy.numpy_msg import numpy_msg
from grasp.msg import vec
import sensor_msgs.point_cloud2 as pc2
from sensor_msgs.msg import PointCloud2
import std_srvs.srv
from shapely.geometry import Polygon

def nothing(x):
    pass

# HSV tuning window
window = 0
if window :
	LMAX  = 50
	hl = 37
	hh = 139
	sl = 70
	sh = 225
	vl = 0
	vh = 255
	cv2.namedWindow('image')
	cv2.createTrackbar('LMAX','image',LMAX,100,nothing)
	cv2.createTrackbar('hl','image',hl,255,nothing)
	cv2.createTrackbar('hh','image',hh,255,nothing)
	cv2.createTrackbar('sl','image',sl,255,nothing)
	cv2.createTrackbar('sh','image',sh,255,nothing)
	cv2.createTrackbar('vl','image',vl,255,nothing)
	cv2.createTrackbar('vh','image',vh,255,nothing)


def feat2rect(x,y,w,h,th):
	al = np.arctan2(h,w)
	diag = np.sqrt(w**2+h**2)
	angle = th + al
	cent = np.array((x,y))
	vec = np.array((diag*np.cos(angle)/2, diag*np.sin(angle)/2))
	vec2 = np.array((w*np.cos(th), w*np.sin(th)))
	pt1x,pt1y = cent - vec
	pt3x,pt3y = cent + vec # opposite points
	pt2x,pt2y = np.array((pt1x,pt1y)) + vec2
	pt4x,pt4y = np.array((pt3x,pt3y)) - vec2
	return np.array((int(pt1x),int(pt1y),int(pt2x),int(pt2y),int(pt3x),int(pt3y),int(pt4x),int(pt4y)))

def rect2img(img0,points,u,v):
	img = np.copy(img0)
	cv2.circle(img,(u,v),3,(255,0,0),-1)
	cv2.line(img,(points[0],points[1]),(points[2],points[3]),(255,0,0),1)
	cv2.line(img,(points[2],points[3]),(points[4],points[5]),(0,255,0),1)
	cv2.line(img,(points[4],points[5]),(points[6],points[7]),(255,0,0),1)
	cv2.line(img,(points[6],points[7]),(points[0],points[1]),(0,255,0),1)
	return img

class baxterGraspNet():
	def __init__(self):
		#ConvNet
		modelFile  = '/home/birl/ros_ws/src/grasp/caffe/graspDeploy.prototxt'
		weightFile = '/home/birl/ros_ws/src/grasp/caffe/caffeGraspTrainX_iter_10000.caffemodel'
		self.graspNet = caffe.Net(modelFile, weightFile, caffe.TEST)
		# blob detector for centering
		params = cv2.SimpleBlobDetector_Params()
		params.minThreshold = 1
		params.maxThreshold = 200
		params.filterByArea = True
		params.minArea = 20
		params.maxArea = 224**2
		self.detector = cv2.SimpleBlobDetector(params)
		# blob detector for  markers
		params = cv2.SimpleBlobDetector_Params()
		params.minThreshold = 1
		params.filterByArea = True
		params.minArea = 1
		self.markDetector = cv2.SimpleBlobDetector(params)
		# Background Subtractor
		self.kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3))
		self.kernel2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3))
		self.MOG     = cv2.BackgroundSubtractorMOG2(100,50,True)
		self.MOG2    = cv2.BackgroundSubtractorMOG2(100,50,True)
		# Camera Topics
		self.cameraTopic = '/camera/rgb/image_color'
		self.depthTopic = '/depthView'
		self.gotCam = 0;
		self.count = 0;
		# Publisher
		self.vecPub = rospy.Publisher("/vec", numpy_msg(vec), queue_size=10)
		self.featPub = rospy.Publisher("/feature", Image, queue_size=10)
		self.viewPub = rospy.Publisher("/view", Image, queue_size=10)
		# Image
		self.display = np.zeros((480,640+480,3), dtype = "uint8")
		# camera
		reset_srv = rospy.ServiceProxy('cameras/reset', std_srvs.srv.Empty)
		rospy.wait_for_service('cameras/reset', timeout = 10)
		reset_srv()
		#self.cameraH = baxter_interface.camera.CameraController("head_camera")
		#self.cameraL = baxter_interface.camera.CameraController("left_hand_camera")
		#self.cameraL.close()
		#self.cameraH.close()
		#camera = baxter_interface.camera.CameraController("right_hand_camera")
		#camera.close()
		#self.cameraL.close()
		#self.cameraH.close()
		#camera.resolution = (int(640),int(400))
		#camera.open()
	
	def sub(self):
		rate = rospy.Rate(60)
		print "Initialize feed"
		# Get kinect view
		# Get depth view
		try:
			rospy.Subscriber(self.depthTopic,  Image, self.depthCallback) #, queue_size=1
		except (rospy.ROSException), error_message:
			print error_message
		try:
			rospy.Subscriber(self.cameraTopic, Image, self.camCallback, queue_size=1) #
		except (rospy.ROSException), error_message:
			print error_message
		print("Starting graspNet procedure. Press Ctrl-C to stop...")
		rospy.spin()
		while not rospy.is_shutdown():
			rate.sleep()


	def camCallback(self,data):
		self.camStream(data)

	def camStream(self, data):
		# print "cam stream"
		bridge = cv_bridge.CvBridge()
		try:
			cv_image = bridge.imgmsg_to_cv2(data,desired_encoding='passthrough')
			self.cam = cv_image
			self.gotCam = 1
		except cv_bridge.CvBridgeError, e:
			print e
		return 0

	def depthCallback(self,data):
		self.depthStream(data)

	def depthStream(self,data):
		# print "depth stream"
		if(self.gotCam):
			bridge = cv_bridge.CvBridge()
			try:
				cv_image = bridge.imgmsg_to_cv2(data,desired_encoding='passthrough')
				self.depth = cv_image
				self.process()
			except cv_bridge.CvBridgeError, e:
				print e
		return 0
	
	def process(self):
		# print "processing"
		mask      = self.MOG.apply(self.cam)
		maskDepth = self.MOG2.apply(self.depth)
		self.count = self.count+1
		if (self.count<100):
			print 'training...'
		elif ((self.count-100)%30 ==0):
			# combine RGBD to RGD
			rgd = np.copy(self.cam)
			rgd[:,:,0] = self.depth[:,:]
			# apply masks
			mask        = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel)
			self.mask  = mask
			maskDepth   = cv2.morphologyEx(maskDepth, cv2.MORPH_OPEN, self.kernel2)
			maskAll     = cv2.bitwise_and(mask,maskDepth)
			rgdM        = cv2.bitwise_and(rgd,rgd,mask = mask)
			rgdMDepth   = cv2.bitwise_and(rgd,rgd,mask = maskDepth)
			rgdMAll     = cv2.bitwise_and(rgd,rgd,mask = maskAll)
			#rgdM        = np.copy(rgd) # do we need BS - yes!
			# crop to 224x224
			rgdMCrop = rgdM[480-224:480, 320-112:320+112]	
			self.rows, self.cols, ch = rgdMCrop.shape
			T = np.float32([[1,0,0],[0,1,-55]])
			self.rgdMCropT = cv2.warpAffine(rgdMCrop,T,(self.cols,self.rows))
			self.centre()
			self.CNN()
			self.feature()
			#self.assess()
			self.publish()
			return 0
			
	def centre(self):
		# print "centre"
		gray       = cv2.cvtColor(cv2.blur(self.rgdMCropT,(50,50)),cv2.COLOR_BGR2GRAY)
		ret,thresh = cv2.threshold(gray,10,255,cv2.THRESH_BINARY_INV)
		keypoints  = self.detector.detect(thresh)
		imageC     = cv2.drawKeypoints(thresh,keypoints,np.array([]),(0,0,255),cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
		self.tx    = 0
		self.ty    = 0
		if len(keypoints)>0:
			print 'found blob'
			self.tx = 112-keypoints[0].pt[0]
			self.ty = 112 - keypoints[0].pt[1]
			T = np.float32([[1,0,self.tx],[0,1,self.ty]])
			self.rgdMCropT = cv2.warpAffine(self.rgdMCropT,T,(self.cols,self.rows))
			print self.tx,self.ty
		cv2.imshow('Displaysdfsd', imageC)
		cv2.waitKey(1)

	def CNN(self):
		# print "Passing to CNN"
		inImg = (self.rgdMCropT.transpose((2,0,1))-144.0)/255
		self.graspNet.blobs['data'].data[...] = inImg
		pred = self.graspNet.forward()
		x,y,w,h,c2,s2 = np.array(pred.values(), dtype='float').reshape(-1)
		self.x = int(x*224)
		self.y = int(y*224)
		self.w = (w*224)
		self.h = (h*224)
		self.u = int(self.x+(320-112)-self.tx)
		self.v = int(self.y+(480-224)+55-self.ty)
		self.th = (np.arctan2(s2,c2))/2
		points=feat2rect(self.u,self.v,self.w,self.h,self.th)
		raw  = rect2img(self.rgdMCropT,feat2rect(self.x,self.y,self.w,self.h,self.th),self.x,self.y)
		full = rect2img(self.cam,feat2rect(self.u,self.v,self.w,self.h,self.th),self.u,self.v)
		self.display[:,-640:,:] = full
		k = 480.0/224.0
		self.display[:,:480,:] = cv2.resize(raw, (0,0), fx=k, fy=k, interpolation = cv2.INTER_CUBIC)
		#cv2.imshow('Display', self.display)
		#cv2.waitKey(1)

	def feature(self):
		print "publishing feature"
		feat = self.cam[self.v-15:self.v+16,self.u-15:self.u+16,:]
		rows,cols,_ = feat.shape
		R = cv2.getRotationMatrix2D((rows/2,cols/2),self.th*180/np.pi,1)
		featR = cv2.warpAffine(feat,R,(rows,cols))
		featmsg = cv_bridge.CvBridge().cv2_to_imgmsg(featR,"bgr8")
		self.featPub.publish(featmsg)
	
	def publish(self):
		print 'u v theta'
		print np.float32(self.u),np.float32(self.v),self.th
		self.vecPub.publish(np.array((np.float32(self.u),np.float32(self.v),np.float32(self.th))))
		displaymsg = cv_bridge.CvBridge().cv2_to_imgmsg(self.display,"bgr8")
		self.viewPub.publish(displaymsg)

	def assess(self):
		imageM = cv2.bitwise_and(self.cam,self.cam,mask = self.mask)
		if window :
			LMAX = cv2.getTrackbarPos('LMAX','image')
			hl = cv2.getTrackbarPos('hl','image')
			hh = cv2.getTrackbarPos('hh','image')
			sl = cv2.getTrackbarPos('sl','image')
			sh = cv2.getTrackbarPos('sh','image')
			vl = cv2.getTrackbarPos('vl','image')
			vh = cv2.getTrackbarPos('vh','image')
		else : 
			hl = 37
			hh = 139
			sl = 70
			sh = 225
			vl = 0
			vh = 255
		#cv2.imshow('imageM', imageM)
		#cv2.waitKey(1)
		hsv = cv2.cvtColor(imageM, cv2.COLOR_BGR2HSV)
		lower_red = np.array([hl,sl,vl])
       		upper_red = np.array([hh,sh,vh])
		mask = cv2.morphologyEx(cv2.inRange(hsv, lower_red, upper_red), cv2.MORPH_OPEN, self.kernel)
		imageM = cv2.bitwise_and(imageM,imageM,mask = mask)
		imageM = cv2.blur(imageM,(5,5))
		cv2.imshow('a',imageM)
		gray = cv2.cvtColor(imageM,cv2.COLOR_BGR2GRAY)
		ret,thresh = cv2.threshold(gray,10,255,cv2.THRESH_BINARY_INV)
		keypoints = self.markDetector.detect(thresh)
		dw = 25
		dh = 14
		if len(keypoints)>0:
			print 'keypoints'
			grasps = []
			thetaA = []
			imageC = cv2.drawKeypoints(self.cam,keypoints,np.array([]),(0,0,255),cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
			if len(keypoints)>1:
				print len(keypoints)
				for i in range(0,len(keypoints)-1):
					for k in range(1,len(keypoints)-i):
						x1 = int(keypoints[i].pt[0]  +(320-112)  -self.tx)
						x2 = int(keypoints[i+k].pt[0]+(320-112)  -self.tx)
						y1 = int(keypoints[i].pt[1]  +(480-224)  -self.ty)
						y2 = int(keypoints[i+k].pt[1]+(480-224)  -self.ty)
						Y = keypoints[i+k].pt[1]-keypoints[i].pt[1]
						X = keypoints[i+k].pt[0]-keypoints[i].pt[0]
						L = np.sqrt(X**2 + Y**2)
						cv2.circle(self.cam,(x1,y1),5,(0,0,255),-1)
						if L<LMAX:
						
							#cv2.line(cv_image,(int(keypoints[i].pt[0]),int(keypoints[i].pt[1])),(int(keypoints[i+1].pt[0]),int(keypoints[i+1].pt[1])),(0,255,0))
							alpha = np.arctan2(Y,X)
							dth = alpha - np.pi/2 
							L = np.sqrt(X**2 + Y**2)
							print L
							N = int(np.floor(L/5))
							for j in range(0,N):
								dx = x1 + np.cos(alpha)*j*L/N
								dy = y1 + np.sin(alpha)*j*L/N
								imageC = rect2img(self.cam,feat2rect(dx,dy,dw,dh,dth),int(dx),int(dy))
								a = feat2rect(dx,dy,dw,dh,dth)
								grasps.append(Polygon([(a[0],a[1]),(a[2],a[3]),(a[4],a[5]),(a[6],a[7])]))
								thetaA.append(dth)
							#thresh = rect2image(thresh,feat2rect(x,y,w,h,th),int(x),int(y))
			else:
				x1 = int(keypoints[0].pt[0]+(320-112)-self.tx)
				y1 = int(keypoints[0].pt[1]+(480-224)-self.ty)
				for i in range(0,10):
					dth = np.pi*i/10
					imageC = rect2img(self.cam,feat2rect(x1,y1,dw,dh,dth),int(x1),int(y1))
					a = feat2rect(x1,y1,dw,dh,dth)
					grasps.append(Polygon([(a[0],a[1]),(a[2],a[3]),(a[4],a[5]),(a[6],a[7])]))
					thetaA.append(dth)
			if len(grasps)>0:
				a = feat2rect(self.u,self.v,self.w,self.h,self.th)
				output = Polygon([(a[0],a[1]),(a[2],a[3]),(a[4],a[5]),(a[6],a[7])])
				AIF = np.zeros((len(grasps),1))
				thEr = np.zeros((len(grasps),1))
				grasp = np.asarray(grasps)
				thh= np.asarray(thetaA)
				for i in range(0,len(grasps)):
					AIF[i] = grasp[i].intersection(output).area
					a = abs(self.th - thh[i])
					thEr[i] = np.arctan2(np.sin(2*a),np.cos(2*a))/2
				areaMx = np.amax(AIF)
				ind = np.argmax(AIF)
				aif = areaMx/output.area
				thdif = thEr[ind]
				print 'area intersection factor'
				print aif
				print 'theta error'
				print thdif
				self.cam = imageC
				
		else: 
			print 'no keypoints' 
		cv2.imshow('imagesfsfds', self.cam)
		cv2.waitKey(1)
		cv2.imshow('image', thresh)
		cv2.waitKey(1)

def main(args):
	rospy.init_node('graspNet', anonymous=True)
	baxter = baxterGraspNet()
	baxter.sub()
	return 0

if __name__ == '__main__':
	main(sys.argv)
