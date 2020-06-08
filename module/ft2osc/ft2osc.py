#!/usr/bin/env python

# ft2osc streams raw data from the fieldtrip buffer according to the OSC protocol
#
# This software is part of the EEGsynth project, see <https://github.com/eegsynth/eegsynth>.
#
# Copyright (C) 2017-2020 EEGsynth project
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
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import configparser
import argparse
import os
import redis
import sys
import time
import numpy as np 

if sys.version_info < (3,6):
    import OSC
else:
    from pythonosc import udp_client

if hasattr(sys, 'frozen'):
    path = os.path.split(sys.executable)[0]
    file = os.path.split(sys.executable)[-1]
    name = os.path.splitext(file)[0]
elif __name__=='__main__' and sys.argv[0] != '':
    path = os.path.split(sys.argv[0])[0]
    file = os.path.split(sys.argv[0])[-1]
    name = os.path.splitext(file)[0]
elif __name__=='__main__':
    path = os.path.abspath('')
    file = os.path.split(path)[-1] + '.py'
    name = os.path.splitext(file)[0]
else:
    path = os.path.split(__file__)[0]
    file = os.path.split(__file__)[-1]
    name = os.path.splitext(file)[0]

# eegsynth/lib contains shared modules
sys.path.insert(0, os.path.join(path,'../../lib'))
import EEGsynth
import FieldTrip


def _setup():
    '''Initialize the module
    This adds a set of global variables
    '''
    global parser, args, config, r, response, patch, ft_host, ft_port, ft_input,monitor

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inifile", default=os.path.join(path, name + '.ini'), help="name of the configuration file")
    args = parser.parse_args()

    config = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
    config.read(args.inifile)

    try:
        r = redis.StrictRedis(host=config.get('redis', 'hostname'), port=config.getint('redis', 'port'), db=0, charset='utf-8', decode_responses=True)
        response = r.client_list()
    except redis.ConnectionError:
        raise RuntimeError("cannot connect to Redis server")

    # combine the patching from the configuration file and Redis
    patch = EEGsynth.patch(config, r)

    # this can be used to show parameters that have changed
    monitor = EEGsynth.monitor(name=name, debug=patch.getint('general','debug'))

    try:
        ft_host = patch.getstring('fieldtrip', 'hostname')
        ft_port = patch.getint('fieldtrip', 'port')
        monitor.success('Trying to connect to buffer on %s:%i ...' % (ft_host, ft_port))
        ft_input = FieldTrip.Client()
        ft_input.connect(ft_host, ft_port)
        monitor.success('Connected to input FieldTrip buffer')
    except:
        raise RuntimeError("cannot connect to input FieldTrip buffer")


    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print('LOCALS: ' + ', '.join(locals().keys()))


def _start():
    '''Start the module
    This uses the global variables from setup and adds a set of global variables
    '''
    global parser, args, config, r, response, patch, name, ft_host, ft_port, ft_input,timeout,hdr_input,begsample,endsample,channame,chanidx,chanosc
    global monitor, debug, s,start, i, j,begsample,endsample
    global s,list_input,list_output,window

    # this is the timeout for the FieldTrip buffer
    timeout = patch.getfloat('fieldtrip', 'timeout', default=30)

    

    hdr_input = None
    start = time.time()
    while hdr_input is None:
        monitor.info('Waiting for data to arrive...')
        if (time.time()-start) > timeout:
            raise RuntimeError("timeout while waiting for data")
        time.sleep(0.1)
        hdr_input = ft_input.getHeader()

    monitor.info("Data arrived")
    monitor.debug(hdr_input)
    monitor.debug(hdr_input.labels)

    window = patch.getint('processing', 'window', default=2)
    

    # combine the patching from the configuration file and Redis
    patch = EEGsynth.patch(config, r)

    # this can be used to show parameters that have changed
    monitor = EEGsynth.monitor(name=name, debug=patch.getint('general','debug'))

    # get the options from the configuration file
    debug = patch.getint('general', 'debug')

    try:
        if sys.version_info < (3,6):
            s = OSC.OSCClient()
            s.connect((patch.getstring('osc','hostname'), patch.getint('osc','port')))
        else:
            s = udp_client.SimpleUDPClient(patch.getstring('osc','hostname'), patch.getint('osc','port'))
        monitor.success('Connected to OSC server')
    except:
        raise RuntimeError("cannot connect to OSC server")

    # channels should be present in both the input and output section of the *.ini file
    list_input  = config.items('input')
    list_output = config.items('output')

    channame = [] # the channel name that matches in the input and output section of the *.ini file
    chanidx = [] # the channel number in the ft buffer
    chanosc = [] # the key name in OSC
    for i in range(len(list_input)):
        for j in range(len(list_output)):
            if list_input[i][0]==list_output[j][0]:
                channame.append(list_input[i][0])  # short name in the ini file
                chanidx.append(patch.getint('input', list_input[i][0])-1)  # channel number
                chanosc.append(list_output[j][1]) # osc topic

    begsample = -1
    endsample = -1

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print('LOCALS: ' + ', '.join(locals().keys()))


def _loop_once():
    '''Run the main loop once
    This uses the global variables from setup and start, and adds a set of global variables
    '''
    global monitor, patch,window
    global hdr_input,ft_input,chanidx,chanosc,channame,begsample,endsample
    global s

    hdr_input = ft_input.getHeader()
    if (hdr_input.nSamples - 1) < endsample:
        raise RuntimeError("buffer reset detected")
    if hdr_input.nSamples < window:
        # there are not yet enough samples in the buffer
        monitor.info("Waiting for data...")
        return

    # get the most recent data segment
    begsample = hdr_input.nSamples - window
    endsample = hdr_input.nSamples - 1
    dat = ft_input.getData([begsample, endsample]).astype(np.double)
    
    monitor.info("Getting {} samples from Fieldtrip buffer...".format(window))

    ## Send the data over OSC 
    for idx,osctopic in enumerate(chanosc):
        curdata = dat[:,chanidx[idx]]

        Dstr = np.array2string(curdata,separator=',',prefix='"',suffix = '"')
        s.send_message(osctopic,Dstr)

        monitor.update(osctopic, curdata[0])

    time.sleep(patch.getfloat('general', 'delay'))


def _loop_forever():
    '''Run the main loop forever
    '''
    while True:
        _loop_once()


def _stop():
    '''Stop and clean up on SystemExit, KeyboardInterrupt
    '''
    global monitor, trigger, ft_input

    ft_input.disconnect()
    monitor.success('Disconnected from input FieldTrip buffer')

    sys.exit()


if __name__ == '__main__':
    _setup()
    _start()
    try:
        _loop_forever()
    except Exception as e:
        print(e)
        _stop()
