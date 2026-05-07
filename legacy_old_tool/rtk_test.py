import socket

server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )

ip = '192.168.30.1'
port = 9901

server_socket.bind((ip, port))
server_socket.listen(5)

conn, addr = server_socket.accept()
print(server_socket.getsockname())
print(addr)
print(server_socket.getsockname())
print(conn)
while True:
    pass