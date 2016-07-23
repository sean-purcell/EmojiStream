#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import argparse
import logging
import socket
import errno
import time
import cv2
import os
from os.path import join, abspath, dirname

from detect.face import locate_face, init_detect, rotate_image
from google.protobuf.message import DecodeError
from proto.conn_pb2 import ConnectionRequest, Packet
from proto.dataupdates_pb2 import ImageHeader, ImageBlock, FaceData, DataUpdate

def ParseArgs():
    parser = argparse.ArgumentParser(description='💻 🎥 📞 📡 😀')
    parser.add_argument('--server', type=str, default='xn--5k8hst.seanp.xyz')
    parser.add_argument('--port', type=int, default=36530)

    root = logging.getLogger('')
    handler = logging.StreamHandler()
    f = logging.Formatter(
        '[%(name)s:%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] '\
        '%(message)s') 
    handler.setFormatter(f)
    handler.setLevel(logging.DEBUG)
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    return parser.parse_args()

class Client(object):
    SEND_FREQ = 5

    def __init__(self):
        self.camera =  cv2.VideoCapture(0)
        self.framenum = 0
        self.detected = ()

        faces_path = join(dirname(abspath(__file__)),
            '../../data/images/emojis.png')
        self.faces = cv2.imread(faces_path, -1)
        self.smiley_face = self.faces[3*72:4*72,0:72]

        self.bg_img = None

        self.sock = None

        classifier_path = join(dirname(abspath(__file__)),
            '../../data/haar/haarcascade_frontalface_default.xml')
        init_detect(classifier_path)


    def Connect(self, ident, addr):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0)
        self.server_addr = addr

        conn = ConnectionRequest(identifier=ident)
        packet = conn.SerializeToString()

        while True:
            self.sock.sendto(chr(0x55) + packet, addr)
            logging.debug('send packet to %s', addr)
            try:
                data, addr = self.sock.recvfrom(1024)
                break
            except (socket.timeout, socket.error), e:
                if isinstance(e, socket.error) and e.errno != errno.EAGAIN:
                    logging.exception('Socket error:')
                    raise
            time.sleep(1)
        try:
            req = ConnectionRequest()
            req.ParseFromString(data)
            self.other_user = req
        except DecodeError:
            logging.exception('Invalid connection data received')
            raise

    def SendData(self):
        """Extracts and sends face position data to other client."""
        data = DataUpdate()
        ret, img = self.camera.read()

        if self.framenum % 5 == 0:
            ndetected = locate_face(img)
            if len(ndetected):
                detected = ndetected
        self.framenum += 1
        if len(detected):
            x = detected[0] + detected[2] / 2
            y = detected[1] + detected[3] / 2

            width = detected[2]
            height = detected[3]
            size = max(abs(width), abs(height))

            update = DataUpdate(
                facedata=FaceData(
                    emoji=FaceData.HAPPY,
                    x=x,
                    y=y,
                    size = int(size)
                ))
            logging.info('sending message to %s:', self.other_user.uid)
            logging.info('x: %s, y: %s', x, y)
            p = Packet(packet=update.SerializeToString(), uid=self.other_user.uid)
            self.sock.sendto(chr(0) + p.SerializeToString(), self.server_addr)
        
    def ParsePacket(self, data):
        packet = Packet()
        data = DataUpdate()
        try:
            packet.ParseFromString(data)
            data.ParseFromString(packet.packet)
        except DecodeError:
            logging.exception('Invalid packet')
            return

        if data.facedata is not None:
            self.next_face = data.facedata

        if self.img_hdr is not None:
            hdr = self.img_hdr
            shape = (hdr.width, hdr.height, 3)
            if self.bg_img is not None and self.bg_img.shape != shape:
                self.bg_img = np.ndarray(shape=(hdr.width, hdr.height, 3),
                    dtype='uint8')

        if self.img_block is not None:
            block = self.img_block
            idx = 0
            bg_img = self.bg_img
            width, height = bg_img.shape[:2]
            if block.left + block.width < width and \
                    block.top + block.height < height:
            
                for x in xrange(block.left, block.left+block.width):
                    for y in xrange(block.top, block.top+block.height):
                        for i in xrange(3):
                            bg_img[x,y,i] = block.pixels[idx]
                            idx += 1


    def TryReceive(self):
        # max 10 packets per frame
        for i in xrange(10):
            try:
                data, addr = self.sock.recvfrom(1024)
                self.ParsePacket(data)
            except (socket.timeout, socket.error), e:
                if e.errno == errno.EAGAIN or isinstance(e, socket.timeout):
                    break
                else:
                    raise 

    def RenderFrame(self):
        self.current_face = self._InterpolateFaceData(self.current_face,
                                                        self.target_face)

        face = cv2.resize(self.smiley_face,
                          dsize=(self.current_face.size,
                                 self.current_face.size),
                          interpolation = cv2.INTER_CUBIC)

        ret, img = self.camera.read()
        x = self.current_face.x
        y = self.current_face.y
        face = rotate_image(face, 0)
        width, height = current_face.shape[:2]
        a = width/2
        b = width - width/2

        try:
            for c in range(0,3):
                img[y-a:y+b, x-a:x+b, c] = \
                face[:,:,c] * (face[:,:,3]/255.0) +  img[y-a:y+b, x-a:x+b, c] * (1.0 - face[:,:,3]/255.0)
        except ValueError:
            pass

        # Display the resulting frame
        cv2.imshow('silly video chat', img)

    def SendReceiveLoop(self):
        while True:
            self.TryReceive()
            self.SendData()
            self.RenderFrame()

    @staticmethod
    def _InterpolateFaceData(current, target):
        """Exactly what it says on the tin.

        Args:
            current: FaceData
            target: FaceData
        Returns:
            FaceData
    """
        f = lambda a, b : a + int(math.ceil((b-a)/5.0))
        return FaceData(
            emoji = target.emoji,
            x = f(current.x, target.x),
            y = f(current.y, target.y),
            theta = f(current.theta, target.theta),
            size =f(current.size, target.size)
        )


def main(args):
    print 'Identifier:',
    ident = raw_input()

    server_addr = (args.server, args.port)
    client = Client()
    client.Connect(ident, server_addr)

    logging.debug('connection to %s, %s',
                  client.other_user.ipaddr,
                  client.other_user.port)
    client.SendReceiveLoop()

if __name__ == '__main__':
    args = ParseArgs()
    main(args)
