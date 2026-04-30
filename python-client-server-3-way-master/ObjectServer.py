import socket
import pickle
from twh import ThreeWayHandshake
# from gc import enable
from time import sleep
SERVER_ADDRESS = "192.168.10.11"
SERVER_PORT = 5000
hanler = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
address = (SERVER_ADDRESS, SERVER_PORT)
print(f"server {SERVER_ADDRESS} at port {SERVER_PORT}")
hanler.bind(address)
hanler.listen(1)


def main():
    con = (hanler.accept()[0])
    connection = False
    while connection != True:
        print("wating for connection")
        # sleep(3)
        data = con.recv(4096)
        obj = pickle.loads(data)
        del data
        print("recieved.")
        obj.Connection()
        print("server side:", obj)
        con.sendall(pickle.dumps(obj))
        connection = obj.IsConnected()
    print("3-way done!!!")
    con.close()


# enable()
main()
