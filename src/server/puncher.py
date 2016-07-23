import socket
import sys
import argparse
import time
import logging

from google.protobuf.message import DecodeError

from proto.conn_pb2 import ConnectionRequest

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

def parse_request(data, addr):
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

    return req

def connect_users(user1, user2, sock):
    packet1 = user2.SerializeToString()
    packet2 = user1.SerializeToString()

    sock.sendto(packet1, (user1.ipaddr, user1.port))
    sock.sendto(packet2, (user2.ipaddr, user2.port))

def register(user_dict, user_data):
    logging.info('registering user for identifier %s', user_data.identifier)
    user_dict[user_data.identifier] = user_data

def server_loop(sock):
    user_dict = {}
    while True:
        data, addr = sock.recvfrom(1024)
        user_data = parse_request(data, addr)
        if user_data:
            ident = user_data.identifier
            if ident in user_dict:
                user2 = user_dict[ident]
                if time.time() - user2.time > TIMEOUT:
                    register(user_dict, user_data)
                elif (user2.ipaddr, user2.port) == \
                        (user_data.ipaddr, user_data.port):
                    register(user_dict, user_data)
                else:
                    logging.info('connecting users with identifier %s', ident)
                    connect_users(user_dict[ident], user_data, sock)
                    user_dict.pop(ident)
            else:
                register(user_dict, user_data)

def main():
    args = configure()

    server = socket.socket(socket.AF_INET,
        socket.SOCK_DGRAM)

    server.bind((UDP_IP, args.port))

    server_loop(server)

if __name__ == '__main__':
    main()

