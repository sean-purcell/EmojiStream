#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import argparse
import logging
import socket
import errno
import time

from proto.conn_pb2 import ConnectionRequest
from google.protobuf.message import DecodeError

def configure():
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

def connect(ident, addr):
    conn = ConnectionRequest(identifier=ident)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1)
    packet = conn.SerializeToString()

    while True:
        sock.sendto(packet, addr)
        logging.debug('send packet to %s', addr)
        try:
            data, addr = sock.recvfrom(1024)
            break
        except socket.timeout:
            pass
    try:
        req = ConnectionRequest()
        req.ParseFromString(data)
        return sock, req
    except DecodeError:
        logging.exception('Invalid connection data received')
        raise

def chat_loop(sock, ouser):
    sock.settimeout(0.5)
    oaddr = (ouser.ipaddr, ouser.port)
    while True:
        logging.info('sending message to %s', oaddr)
        sock.sendto('yoo', oaddr)
        data, addr = None, None
        try:
            data, addr = sock.recvfrom(10)
        except (socket.timeout, socket.error), e:
            if e.errno == errno.EAGAIN or isinstance(e, socket.timeout):
                pass
            else:
                raise
        if data:
            logging.info('Recevied message from %s: %s', addr, data)
        time.sleep(0.5)

def main(args):
    print 'Identifier:',
    ident = raw_input()

    sock, ouser = connect(ident, (args.server, args.port))

    logging.debug('connection to %s, %s', ouser.ipaddr, ouser.port)
    chat_loop(sock, ouser)

if __name__ == '__main__':
    args = configure()
    main(args)

