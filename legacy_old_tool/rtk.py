import socket


def start_client(host='192.168.0.5', port=9901):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.sendall(b'Hello, server!')
        data = s.recv(1024)
    print(f"Received: {data.decode()}")


if __name__ == '__main__':

    socket.inet_aton("192.168.30.1")