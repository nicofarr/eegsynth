import numpy as np
from pythonosc import udp_client

s = udp_client.SimpleUDPClient('localhost', 5014)

arrayrange = 10000*np.arange(10)
arrayrange_float = np.arange(10,dtype=np.float) + 0.4627428

D_string = np.array2string(arrayrange,separator=',',prefix='"',suffix = '"')

s.send_message("/ft/test",D_string)

D_string = np.array2string(arrayrange_float,separator=',',prefix='"',suffix = '"')

s.send_message("/ft/test",D_string)