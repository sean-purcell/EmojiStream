import sys
import cv2

from detect.face import locate_face, init_detect

camera =  cv2.VideoCapture(0)

def main():
    framenum = 0
    init_detect(sys.argv[1])

    detected = ()

    while True:
        ret, img = camera.read()


        if framenum % 5 == 0:
            ndetected = locate_face(img)
            if len(ndetected):
                detected = ndetected
        framenum += 1
        if len(detected):
            x = detected[0] + detected[2] / 2
            y = detected[1] + detected[3] / 2
            cv2.circle(img, (x, y), 50, (255, 0, 0))
        # Display the resulting frame
        cv2.imshow('Video', img)
        res = cv2.waitKey(1)
        if cv2.waitKey(1) == ord('q'):
            break

if __name__ == '__main__':
    main()
