#!/usr/bin/env python
#
# This software is part of the EEGsynth project, see https://github.com/eegsynth/eegsynth
#
# Copyright (C) 2017 EEGsynth project
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import configparser
import argparse
import math
import multiprocessing
import numpy as np
import os
import redis
import sys
import threading
import time

if sys.version_info < (3,6):
    import OSC
else:
    from pythonosc import udp_client


if hasattr(sys, 'frozen'):
    basis = sys.executable
elif sys.argv[0]!='':
    basis = sys.argv[0]
else:
    basis = './'
installed_folder = os.path.split(basis)[0]

# eegsynth/lib contains shared modules
sys.path.insert(0, os.path.join(installed_folder, '../../lib'))
import EEGsynth
import FieldTrip

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--inifile", default=os.path.join(installed_folder, os.path.splitext(os.path.basename(__file__))[0] + '.ini'), help="optional name of the configuration file")
args = parser.parse_args()

config = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
config.read(args.inifile)

try:
    r = redis.StrictRedis(host=config.get('redis', 'hostname'), port=config.getint('redis', 'port'), db=0)
    response = r.client_list()
except redis.ConnectionError:
    print("Error: cannot connect to redis server")
    exit()

# combine the patching from the configuration file and Redis
patch = EEGsynth.patch(config, r)

# this determines how much debugging information gets printed
debug = patch.getint('general','debug')

# this is the timeout for the FieldTrip buffer
timeout = patch.getfloat('fieldtrip', 'timeout')


try:
    if sys.version_info < (3,6):
        s = OSC.OSCClient()
        s.connect((patch.getstring('osc','hostname'), patch.getint('osc','port')))
    else:
        s = udp_client.SimpleUDPClient(patch.getstring('osc','hostname'), patch.getint('osc','port'))
    print('Connected to OSC server')
except:
    raise RuntimeError("cannot connect to OSC server")


try:
    ftc_host = patch.getstring('fieldtrip','hostname')
    ftc_port = patch.getint('fieldtrip','port')
    if debug>0:
        print('Trying to connect to buffer on %s:%i ...' % (ftc_host, ftc_port))
    ftc = FieldTrip.Client()
    ftc.connect(ftc_host, ftc_port)
    if debug>0:
        print("Connected to FieldTrip buffer")
except:
    print("Error: cannot connect to FieldTrip buffer")
    exit()

hdr_input = None
start = time.time()
while hdr_input is None:
    if debug>0:
        print("Waiting for data to arrive...")
    if (time.time()-start)>timeout:
        print("Error: timeout while waiting for data")
        raise SystemExit
    hdr_input = ftc.getHeader()
    time.sleep(0.2)

if debug>0:
    print("Data arrived")
if debug>1:
    print("Headers:",hdr_input)
    print("Labels : ", hdr_input.labels)

channel_items = config.items('input')
channame = []
chanindx = []
for item in channel_items:
    # channel numbers are one-offset in the ini file, zero-offset in the code
    channame.append(item[0])
    chanindx.append(patch.getint('input', item[0])-1)

if debug>0:
    print(channame, chanindx)


window      = int(patch.getfloat('processing','window'))  # in samples

begsample = -1
endsample = -1

while True:
    time.sleep(patch.getfloat('general', 'delay'))

    hdr_input = ftc.getHeader()
    if (hdr_input.nSamples-1)<endsample:
        print("Error: buffer reset detected")
        raise SystemExit
    endsample = hdr_input.nSamples - 1
    if endsample<window:
        # not enough data, try again in the next iteration
        print("NOT ENOUGH DATA")
        continue

    begsample = endsample-window+1
    D = ftc.getData([begsample, endsample])

    D = D[:, chanindx]


## Send to OSC

    if sys.version_info < (3,6):
        msg = OSC.OSCMessage("/ft/eeg1") 
        msg.append(list(D[:,0]))
        s.send(msg)

        msg = OSC.OSCMessage("/ft/eeg2") 
        msg.append(list(D[:,1]))
        s.send(msg)
    else:

        ## Rescaling and converting to int
        scale = 10000
        D= (scale * D).astype(np.int)

        Dstr = np.array2string(D[:,0],separator=',',prefix='"',suffix = '"')
        s.send_message("/ft/eeg1", Dstr)

        Dstr = np.array2string(D[:,1],separator=',',prefix='"',suffix = '"')
        s.send_message("/ft/eeg2", Dstr)

        Dstr = np.array2string(D[:,2],separator=',',prefix='"',suffix = '"')
        s.send_message("/ft/eeg3", Dstr)

        Dstr = np.array2string(D[:,3],separator=',',prefix='"',suffix = '"')
        s.send_message("/ft/eog", Dstr)

        Dstr = np.array2string(D[:,4],separator=',',prefix='"',suffix = '"')
        s.send_message("/ft/ecg", Dstr)
        



# send it as a string with a space as separator
                        
