import socket
import sys
      # Create a TCP/IP socket.
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

      # Bind the socket to the port.
server_address = ('localhost', 11111)
##print('starting up on {} port {}'.format( server_address))
                                                              
sock.bind(server_address)

      # Listen for incoming connections.
sock.listen(5)


class PythonSwitch:
    def switch( self,inp):
        default="gggg"
        print("default",inp)
        return getattr(self, 'case_' + str(inp), lambda: default)()
        
    def case_1(self):
        print("case 1 called")
        return
    def case_2(self):
        print("case 2 calle")
        return

while True:
            # Wait for a connection.
    print('waiting for a connection')
    connection, client_address = sock.accept()
    try:
        while True:
                data = connection.recv(1048)
                print('received {!r} from client'.format(data))
                print(data[0])##cases
                print(data[1])
                print("heyy")
                if data:
                    s=PythonSwitch()
                    s.switch(data[0])
                    Ackbackmsg=[1,]
                    byte_array=bytearray(Ackbackmsg)
                    connection.sendall(byte_array)
                    
                    
                
               
##                if data:
##                    ##print('sending data back to the client')
##                    connection.sendall(data)
##                else:
##                    ##print('no data from', client_address)
##                    break

    finally:
                # Clean up the connection.
        connection.close()
