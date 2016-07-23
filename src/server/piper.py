import socket
import sys
import argparse
import time
import logging
import struct
import os

from google.protobuf.message import DecodeError

from proto.conn_pb2 import ConnectionRequest, Packet

UDP_IP = '0.0.0.0'
TIMEOUT = 10

def configure():
    parser = argparse.ArgumentParser(description=
        'Router server for emoji video chat')
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

def parse_signup(data, addr):
    logging.info('Received request of len %s from %s', len(data), addr)
    try:
        req = ConnectionRequest()
        req.ParseFromString(data)
    except DecodeError:
        logging.exception('Failed to decode')
        return None

    req.ipaddr = addr[0]
    req.port = addr[1]
    req.time = time.time()
    req.uid = struct.unpack("<Q", os.urandom(8))[0]

    return req

def connect_users(user1, user2, sock, uid_map):
    packet1 = user2.SerializeToString()
    packet2 = user1.SerializeToString()

    uid_map[user1.uid] = user1
    uid_map[user2.uid] = user2

    sock.sendto(packet1, (user1.ipaddr, user1.port))
    sock.sendto(packet2, (user2.ipaddr, user2.port))

def register(user_dict, user_data):
    logging.info('registering user for identifier %s', user_data.identifier)
    user_dict[user_data.identifier] = user_data

def pass_message(data, uid_map, sock):
    try:
        p = Packet()
        p.ParseFromString(data)
        target = uid_map[p.uid]
        p.uid = target.uid
        packet = p.SerializeToString()
        sock.sendto(packet, (target.ipaddr, target.port))
        logging.debug('passing message of len %s to %s',
            len(packet), p.uid)
    except:
        logging.exception('Failed to pass message')

def server_loop(sock):
    waiting_dict = {}
    uid_map = {}
    while True:
        data, addr = sock.recvfrom(1024)
        if ord(data[0]) == 0x55: # SIGNUP MAGIC NUMBER
            user_data = parse_signup(data[1:], addr)
            if user_data:
                ident = user_data.identifier
                if ident in waiting_dict:
                    user2 = waiting_dict[ident]
                    if time.time() - user2.time > TIMEOUT:
                        register(waiting_dict, user_data)
                    elif (user2.ipaddr, user2.port) == \
                            (user_data.ipaddr, user_data.port):
                        register(waiting_dict, user_data)
                    else:
                        logging.info('connecting users with identifier %s',
                            ident)
                        connect_users(waiting_dict[ident], user_data, sock,
                            uid_map)
                        waiting_dict.pop(ident)
                else:
                    register(waiting_dict, user_data)
        else:
            pass_message(data[1:], uid_map, sock)

def main():
    args = configure()

    server = socket.socket(socket.AF_INET,
        socket.SOCK_DGRAM)

    logging.info('Starting server on %s', (UDP_IP, args.port))
    server.bind((UDP_IP, args.port))

    server_loop(server)

if __name__ == '__main__':
    main()

