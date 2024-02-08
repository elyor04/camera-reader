import cv2
from HKIPcamera import HKIPcamera

cam = HKIPcamera()
cam.open("192.168.11.250", "admin", "abcd1234")

while True:
    ret, frame = cam.read()
    if not ret:
        continue
    frame = cv2.resize(frame, None, fx=0.5, fy=0.5)

    cv2.imshow("Camera", frame)
    if cv2.waitKey(1) == 27:  # esc
        break

cam.release()
cv2.destroyAllWindows()
