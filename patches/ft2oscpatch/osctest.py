import numpy as np
from pythonosc import udp_client

s = udp_client.SimpleUDPClient('localhost', 5014)


def send_osc(s,D):
    print(D)

    print("Sending values independently")

    s.send_message("/ft/test", D[:].tolist())

    print("Sending values as an array of bytes (hexa)")

    s.send_message("/ft/test", (D[:].tobytes()))
    print("\n")



print('Connected to OSC server')

D = np.arange(15) ### This generates all numbers from 0 to 14


print("Sending Integer Version")
send_osc(s,D)

print("Sending Float16 Version")

D_float = np.float16(D)
send_osc(s,D_float)

print("Sending Float32 Version")

D_float = np.float32(D)
send_osc(s,D_float)

print("Sending String Version")

D_string = np.array2string(D_float)

s.send_message("/ft/test",D_string)
