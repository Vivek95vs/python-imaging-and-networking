import socket
import sys

      # Create a TCP/IP socket.
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

      # Connect the socket to the port where the server is listening.
server_address = ('localhost', 11111)
##print('connecting to {} port {}'.format(*server_address))

sock.connect(server_address)



try:
    message =[1,2]
    byte_array=bytearray(message)
    print('sending {!r} to server'.format(message))
    sock.sendall(byte_array)

           # Look for the response.
    amount_received = 0
    amount_expected = len(message)

    while amount_received < amount_expected:
        data = sock.recv(1048)
        amount_received += len(data)
        print('received {!r} from server'.format(data))
finally:
           print('closing socket')
           sock.close()
