# -*- coding:utf-8 -*-
import os
import time
import socket
from typing import List, Dict, Optional

from threading import Thread

CACHE_SIZE = 70000

class rtk_test:
    def __init__(self):
        self.__server_socket = None
        self.__rtk_ip = "192.168.30.1"
        self.__rtk_port = 9901
        self.thread = None
        self.data: List[Optional[Dict]] = [None] * CACHE_SIZE
        self.__current_index = 0

    @property
    def server_socket(self):
        if self.__server_socket is not None:
            return self.__server_socket
        self.__server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )
        self.__server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            True,
        )
        self.__server_socket.settimeout(10)

        return self.__server_socket

    def start(self):
        with self.server_socket as s:
            s.bind((
                self.__rtk_ip,
                self.__rtk_port,
            ))
            s.listen(5)
            print(s.getsockname())
            while True:
                try:
                    conn, addr = s.accept()
                    print(conn, addr)

                    rtk_save_path = "rtk_test.txt"

                    print(dir(conn))
                    while True:
                        with open(rtk_save_path, "w") as f:
                            self.process_rtk_frame(conn, f)
                except Exception as e:
                    print(e)

    def process_rtk_frame(self, conn, f):
        data = conn.recv(2048).decode("utf-8")
        timestamp = time.time()
        print(timestamp, data)
        if data[:6] == '$GPCHC':
            if data.count('\r\n') > 1:
                dataList = data.split('\r\n')
                for i in range(len(dataList) - 1):
                    d = dataList[i]
                    d += ',{}\n'.format(str(timestamp + 0.01 * i))
                    self.data[self.__current_index] = {
                        "timestamp": timestamp,
                        "data": d,
                    }
                    self.__current_index += 1
                    self.__current_index %= CACHE_SIZE
                    f.write(d)
            else:
                validation_data = data.split(',')
                status = int(validation_data[21])
                if data.splitlines(True):
                    data = data.replace('\r\n', ',{}\n'.format(str(timestamp)))
                self.data[self.__current_index] = {
                    "timestamp": timestamp,
                    "data": data,
                }
                self.__current_index += 1
                self.__current_index %= CACHE_SIZE
                f.write(data)

if __name__ == '__main__':

    test = rtk_test()
    test.start()


