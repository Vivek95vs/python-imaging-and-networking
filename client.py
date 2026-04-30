import cv2
import numpy as np
import socket
import struct
import time

def recvall(sock, count):
    buf = b''
    while count:
        newbuf = sock.recv(count)
        if not newbuf:
            return None
        buf += newbuf
        count -= len(newbuf)
    return buf

def tcp_client(tcp_ip='192.168.10.20', tcp_port=9999):  # Replace with server IP
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((tcp_ip, tcp_port))
    print("[Client] Connected to server")

    try:
        while True:
            ts_bytes = recvall(sock, 8)
            if ts_bytes is None:
                print("[Client] Server disconnected")
                break
            timestamp = struct.unpack('d', ts_bytes)[0]

            length_bytes = recvall(sock, 4)
            if length_bytes is None:
                print("[Client] Server disconnected")
                break
            length = int.from_bytes(length_bytes, byteorder='big')

            frame_data = recvall(sock, length)
            if frame_data is None:
                print("[Client] Server disconnected")
                break

            delay = time.time() - timestamp
            print(f"[Client] Delay: {delay*1000:.1f} ms")

            nparr = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None:
                cv2.imshow('TCP Video Stream (Client)', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    finally:
        sock.close()
        cv2.destroyAllWindows()
        print("[Client] Connection closed")

if __name__ == "__main__":
    tcp_client(tcp_ip='192.168.10.20', tcp_port=9999)
