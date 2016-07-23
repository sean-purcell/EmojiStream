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
from proto.dataupdates_pb2 import ImageHeader, Image, FaceData, DataUpdate

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
    def __init__(self):
        self.camera =  cv2.VideoCapture(0)
        self.framenum = 0
        self.SEND_FREQ = 5
        self.detected = ()

        faces_path = join(dirname(abspath(__file__)),
            '../../data/images/emojis.png')
        self.faces = cv2.imread(faces_path, -1)
        self.smiley_face = self.faces[3*72:4*72,0:72]

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
            self.other_uid = req
        except DecodeError:
            logging.exception('Invalid connection data received')
            raise

    def SendData(self):
        """Extracts and sends face position data to other client."""
        ret, img = camera.read()

        if framenum % 5 == 0:
            ndetected = locate_face(img)
            if len(ndetected):
                detected = ndetected
        framenum += 1
        if len(detected):
            x = detected[0] + detected[2] / 2
            y = detected[1] + detected[3] / 2

            width = detected[2]
            height = detected[3]
            size = max(abs(width), abs(height))
            update = DataUpdate(
                facedata=FaceData(
                    emoji=FaceData.Emoji.HAPPY,
                    x=x,
                    y=y
                ))
            logging.info('sending message to %s:', self.other_uid)
            logging.info('x: %s, y: %s', x, y)
            p = Packet(packet=update.SerializeToString(), uid=self.other_uid)
            self.sock.sendto(chr(0) + p.SerializeToString(), self.server_addr)

    def TryReceive(self):
        # max 10 packets per frame
        for i in xrange(10):
            try:
                data, addr = self.sock.recvfrom(1024)
                self.ReceivePacket(data)
            except (socket.timeout, socket.error), e:
                if e.errno == errno.EAGAIN or isinstance(e, socket.timeout):
                    pass
                else:
                    raise
            if data:
                try:
                    p = Packet()
                    p.ParseFromString(data)
                    logging.info('Recevied message from %s: %s', addr, p.packet)
                except DecodeError:
                    logging.exception('Invalid packet received: %s', data)

    def SendData(self):
        pass

    def RenderFrame(self):
        pass

    def SendReceiveLoop(self):
        while True:
            self.TryReceive()
            self.SendData()
            self.RenderFrame()

def main(args):
    print 'Identifier:',
    ident = raw_input()

    server_addr = (args.server, args.port)
    client = Client()
    client.Connect(ident, server_addr)

    logging.debug('connection to %s, %s',
                  client.other_uid.ipaddr,
                  client.other_uid.port)
    client.SendReceiveLoop()

if __name__ == '__main__':
    args = ParseArgs()
    main(args)
