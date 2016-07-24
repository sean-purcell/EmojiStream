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
import random
import numpy as np
import math
import select
import struct
from os.path import join, abspath, dirname

from detect.face import locate_face, init_detect, rotate_image
from google.protobuf.message import DecodeError
from proto.conn_pb2 import ConnectionRequest, Packet
from proto.dataupdates_pb2 import ImageHeader, ImageBlock, FaceData, \
    DataUpdate, Msg

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
    handler.setLevel(logging.INFO)
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    return parser.parse_args()

class Client(object):
    SEND_FREQ = 5
    BLOCK_SIZE = 17
    BLOCKS_PER_FRAME = 10
    CURS_PER_FRAME = 10
    MESSAGE_DURATION = 10

    def __init__(self):
        self.camera =  cv2.VideoCapture(0)
        self.framenum = 0
        self.detected = ()

        self.current_face = None
        self.target_face = None

        faces_path = join(dirname(abspath(__file__)),
            '../../data/images/emojis.png')
        self.faces = cv2.imread(faces_path, -1)
        self.smiley_face = self.faces[3*72:4*72,0:72]

        self.bg_img = None

        self.outgoing_message_q = ['test']
        self.messages_rendering = [] #(msg, x, y, framesLeft)

        self.sock = None

        self.header_sent = False

        self.unsent_blocks = None
        self.cur_column = 0

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

    def _Send(self, update):
        data = update.SerializeToString()
        logging.debug('sending message of len %s', len(data))
        packet = Packet(uid=self.other_user.uid,
            packet=data)
        self.sock.sendto(chr(0)+packet.SerializeToString(), self.server_addr)

    def SendData(self):
        """Extracts and sends face position data to other client."""

        if not self.header_sent:
            height, width = self.local_img.shape[:2]
            update = DataUpdate(
                img_hdr=ImageHeader(
                    width=width,
                    height=height
                ),
                utype=DataUpdate.IMG_HDR
            )

            for i in xrange(20):
                self._Send(update)
            self.header_sent=True

        detected = ()
        if self.framenum % self.SEND_FREQ == 0:
            img = self.local_img
            detected = locate_face(img)
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
                ),
                utype = DataUpdate.FACEDATA
            )
            logging.debug('x: %s, y: %s', x, y)
            self._Send(update)

        for i in range(self.CURS_PER_FRAME):
            height = self.local_img.shape[0]
            left = self.cur_column*self.BLOCK_SIZE
            width = min(self.BLOCK_SIZE, self.local_img.shape[1] - left)
            block = ImageBlock(
                left=self.cur_column*self.BLOCK_SIZE,
                top=0,
                height=height,
                width=width)
            raw_data = ['\0']*(len(range(0, height, self.BLOCK_SIZE))*3)
            idx = 0
            for y in xrange(0, height, self.BLOCK_SIZE):
                for c in range(3):
                    raw_data[idx] = \
                        chr(int(np.mean(self.local_img[y:y+self.BLOCK_SIZE,left:left+width,c])))
                    idx += 1

            block.pixels = ''.join(raw_data)
            update = DataUpdate(
                img_block=block,
                utype=DataUpdate.IMG_BLOCK
            )
            self._Send(update)
            self.cur_column += 1
            if self.cur_column * self.BLOCK_SIZE > self.local_img.shape[1]:
                self.cur_column = 0
                

#        for i in xrange(self.BLOCKS_PER_FRAME):
#            if not self.unsent_blocks:
#                self.InitBgBlocks()
#            block = random.choice(tuple(self.unsent_blocks))
#            self.unsent_blocks.remove(block)
#            block = ImageBlock(
#                left=block[0],
#                top=block[1],
#                width=block[2],
#                height=block[3])
#            left = block.left
#            left, top = block.left, block.top
#            right, bot = left + block.width, top + block.height
#            arr = self.local_img[top:bot, left:right, :]
#            arr = arr.reshape(block.width*block.height*3)
#            block.pixels = arr.tostring()
#            update = DataUpdate(
#                img_block=block,
#                utype = DataUpdate.IMG_BLOCK)
#            self._Send(update)

    def InitBgBlocks(self):
        height, width = self.local_img.shape[:2]
        self.unsent_blocks = set()
        for x in xrange(0, width, self.BLOCK_SIZE):
            for y in xrange(0, height, self.BLOCK_SIZE):
                bwidth = min(self.BLOCK_SIZE, width - x)
                bheight = min(self.BLOCK_SIZE, height - y)
                self.unsent_blocks.add((
                    x,
                    y,
                    bwidth,
                    bheight))

    def ParsePacket(self, raw_data):
        logging.debug('received packet of len %s', len(raw_data))
        packet = Packet()
        data = DataUpdate()
        try:
            packet.ParseFromString(raw_data)
            data.ParseFromString(packet.packet)
        except DecodeError:
            logging.exception('Invalid packet')
            return

        if data.utype == DataUpdate.MESSAGE:
            if self.bg_img is not None:
                random.seed(data.msg.seed)
                height, width = self.bg_img.shape[:2]
                self.messages_rendering.append(
                    [data.msg.message,
                     random.randint(width/2 - 250, width/2 + 250),
                     random.randint(height/2 - 250, height/2 + 250),
                     self.MESSAGE_DURATION + time.time()])

        if data.utype == DataUpdate.FACEDATA:
            self.target_face = data.facedata

        if data.utype == DataUpdate.IMG_HDR:
            hdr = data.img_hdr
            shape = (hdr.height, hdr.width, 3)
            if self.bg_img is None or self.bg_img.shape != shape:
                self.bg_img = np.ndarray(shape=shape,
                    dtype='uint8')

        if data.utype == DataUpdate.IMG_BLOCK:
            block = data.img_block
            height = self.bg_img.shape[0]
            left = block.left
            width = block.width
            idx = 0
            for y in xrange(0, height, self.BLOCK_SIZE):
                for c in range(3):
                    self.bg_img[y:y+self.BLOCK_SIZE,left:left+width,c] = ord(block.pixels[idx])
                    idx += 1

        if False and data.utype == DataUpdate.IMG_BLOCK:
            block = data.img_block
            if self.bg_img is not None:
                bg_img = self.bg_img
                height, width = bg_img.shape[:2]
                if block.left + block.width < width and \
                        block.top + block.height < height:
                    shape = (block.height, block.width, 3)
                    arr = np.fromstring(block.pixels, dtype='uint8')
                    arr = arr.reshape(shape)
                    left, top = block.left, block.top
                    right, bot = left + block.width, top + block.height
                    self.bg_img[top:bot, left:right, :] = arr

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
        if self.bg_img is None:
            return
        img = self.bg_img.copy()

        if self.target_face is not None:
            if self.current_face is None:
                self.current_face = self.target_face
            self.current_face = self._InterpolateFaceData(self.current_face,
                                                            self.target_face)

            face = cv2.resize(self.smiley_face,
                              dsize=(self.current_face.size,
                                     self.current_face.size),
                              interpolation = cv2.INTER_CUBIC)

            x = self.current_face.x
            y = self.current_face.y
            face = rotate_image(face, 0)
            width, height = face.shape[:2]
            a = width/2
            b = width - width/2

            try:
                for c in range(0,3):
                    img[y-a:y+b, x-a:x+b, c] = \
                    face[:,:,c] * (face[:,:,3]/255.0) +  img[y-a:y+b, x-a:x+b, c] * (1.0 - face[:,:,3]/255.0)
            except ValueError:
                logging.exception("RenderFrame tried to draw outside of the lines")

        for msg in self.messages_rendering:
            cv2.putText(img, msg[0], (msg[1],msg[2]), cv2.FONT_HERSHEY_COMPLEX,
                3, 255, 3)

        self.messages_rendering =filter(lambda l: l[3] > time.time(),
                                        self.messages_rendering)

        # Display the resulting frame
        cv2.imshow('silly video chat', img)

    def CaptureFrame(self):
        ret, img = self.camera.read()
        self.local_img = img

    def TrySendMessage(self):
        res, _, _ = select.select([0], [], [], 0)
        if 0 in res:
            line = raw_input()
            seed = struct.unpack("<Q", os.urandom(8))[0]
            update = DataUpdate(
                msg = Msg(
                    message=line,
                    seed=seed),
                utype = DataUpdate.MESSAGE
            )
            for i in xrange(20):
                self._Send(update)

    def SendReceiveLoop(self):
        while True:
            self.CaptureFrame()
            self.TryReceive()
            self.SendData()
            self.TrySendMessage()
            self.RenderFrame()
            self.framenum += 1
            cv2.waitKey(1)

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
