import cv2
import numpy as np
import glob

CHECKERBOARD = (9,6)  # inner corners per row & column

objp = np.zeros((1, CHECKERBOARD[0]*CHECKERBOARD[1], 3), np.float32)
objp[0,:,:2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1,2)

objpoints = []  # 3D points in real world
imgpoints = []  # 2D points in image

images = glob.glob('calib_images/*.jpg')

for fname in images:
    img = cv2.imread(fname)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD)

    if ret:
        objpoints.append(objp)
        imgpoints.append(corners)

h, w = gray.shape[:2]

K = np.zeros((3, 3))
D = np.zeros((4, 1))

rvecs = []
tvecs = []

cv2.fisheye.calibrate(
    objpoints,
    imgpoints,
    (w, h),
    K,
    D,
    rvecs,
    tvecs,
    cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC
)

print("Camera Matrix (K):")
print(K)

print("\nDistortion Coefficients (D):")
print(D)