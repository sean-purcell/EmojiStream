import sys
import cv2

from detect.face import locate_face, init_detect

camera =  cv2.VideoCapture(0)

def main():
    framenum = 0
    init_detect(sys.argv[1])

    detected = ()

    faces = cv2.imread("../data/images/emojis.png", -1)
    x_offset=y_offset=36
    smiley_face = faces[3*72:4*72,0:72]

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
            
            width = detected[2]
            height = detected[3]
            size = max(abs(width), abs(height))
            a = size/2
            b = size - size/2
            face = cv2.resize(smiley_face, dsize=(size, size), interpolation = cv2.INTER_CUBIC)

            try:
                for c in range(0,3):
                    img[y-a:y+b, x-a:x+b, c] = \
                    face[:,:,c] * (face[:,:,3]/255.0) +  img[y-a:y+b, x-a:x+b, c] * (1.0 - face[:,:,3]/255.0)
            except ValueError:
                pass
            #img[y-y_offset:y+y_offset, x-x_offset:x+x_offset] = face[0:72, 0:72]


        # Display the resulting frame
        cv2.imshow('Video', img)
        res = cv2.waitKey(1)
        if res == ord('q'):
            break

if __name__ == '__main__':
    main()
