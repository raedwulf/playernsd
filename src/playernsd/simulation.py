#
# Copyright (c) 2011, The University of York
# All rights reserved.
# Author(s):
#   Tai Chi Minh Ralph Eastwood <tcmreastwood@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the The University of York nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# ANY ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE UNIVERSITY OF YORK BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

##@file simulation.py
# The simulation class that can communicate with an external executable
# such as ns3 to provide more accurate simulations.

import sys
import subprocess
import thread
import logging
from Queue import Queue
from threading import Thread
from struct import *

log = logging.getLogger('playernsd')

## Message type for communication over the stdin/stdout with the executable.
class MessageType:
  NEW_CLIENT = 0
  SEND = 1
  RECV = 2
  DISCONNECT = 3
  PROPGET = 4
  PROPSET = 5
  PROPVAL = 6

## Writer thread to write messages to stdout (or any stream).
class Writer(Thread):
  ## Initialise the data for a stdout (or any stream) writer.
  # @param self The playernsd::simulation::Writer instance.
  # @param stream The stdout for writing to.
  def __init__(self, stream):
    self.send_queue = Queue()
    self.stream = stream
    Thread.__init__(self)
  ## Setting a property value in the target executable.
  # @param self The playernsd::simulation::Writer instance.
  # @param prop The property name.
  # @param val The property value.
  def prop_set(self, prop, val):
    log.debug("SIMPROPSET " + prop + ":" + val)
    self.send_queue.put(pack('<BI', MessageType.PROPSET,
      len(prop) + len(val) + 2) + prop + '\0' + val + '\0')
  ## Getting a property value from the target executable.
  # @param self The playernsd::simulation::Writer instance.
  # @param _from The client that asked this.
  # @param prop The property name.
  def prop_get(self, _from, prop):
    log.debug("SIMPROPGET " + prop)
    self.send_queue.put(pack('<BII', MessageType.PROPGET, _from,
      len(prop)+1) + prop + '\0')
  ## Send a message in the target executable.
  # @param self The playernsd::simulation::Writer instance.
  # @param _from The client that the message comes from.
  # @param to The client that the messagesa is being sent to.
  # @param msg The message to be sent.
  def send(self, _from, to, msg):
    data = pack('<BIII', MessageType.SEND,
              _from, to, len(msg)) + msg
    log.debug("SIMSEND(%d->%d) %s" % (_from, to,
      data.encode(sys.stdout.encoding,
        'backslashreplace').replace('\n', '\\n')))
    self.send_queue.put(data)
  ## Disconnect from the socket.
  # @param self The playernsd::simulation::Writer instance.
  # @param socket The socket that is disconnecting.
  def disconnect(self, socket):
    data = pack('<BI', MessageType.DISCONNECT, socket)
    log.debug("SIMDISCONNECT(%d)" % socket)
    self.send_queue.put(data)
  ## Queue processing worker routine.
  # @param self The playernsd::simulation::Writer instance.
  def run(self):
    while True:
      msg = self.send_queue.get()
      # Empty message means quit thread.
      if len(msg) == 0:
        break
      self.stream.write(msg);
      self.send_queue.task_done()
  ## Stop the writer thread.
  def stop(self):
    self.send_queue.put('')

## Simulation thread for controlling the simulation executable.
class Simulation(Thread):
  ## Initialise this class.
  # @param self The playernsd::simulation::Simulation instance.
  # @param process The process to run and execute to simulate.
  # @param recv_callback The callback to call when a message is recevied.
  # @param prop_val_callback The callback to call when a property
  #        value is received.
  def __init__(self, process, recv_callback, prop_val_callback):
    self.cidi = {'__broadcast__':0}
    self.cidt = ['__broadcast__']
    self.cidn = 1
    self.recv_callback = recv_callback
    self.prop_val_callback = prop_val_callback
    self.process = process
    Thread.__init__(self)
    self.p = subprocess.Popen(self.process,
      stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    self.writer = Writer(self.p.stdin)
    self.writer.daemon = True
    self.writer.start()
  ## Add new client.
  #
  # This typically can only added up to some application defined limit of
  # maximum clients.
  # @param self The playernsd::simulation::Simulation instance.
  # @param clientid Client ID of client added.
  def new_client(self, clientid):
    self.cidi[clientid] = self.cidn
    self.cidt.append(clientid)
    self.cidn += 1
  ## Remove a client.
  #
  # This is unsupported, because external simulations usually need pre-configured
  # networks.
  def remove_client(self, clientid):
    pass
  ## Send a message in the target executable.
  # @param self The playernsd::simulation::Simulation instance.
  # @param _from The client that the message comes from.
  # @param to The client that the messagesa is being sent to.
  # @param msg The message to be sent.
  def send(self, _from, to, message):
    self.writer.send(self.cidi[_from], self.cidi[to], message)
  ## Substitute the property name using the _from parameter.
  #
  # This allows property names using the 'self.' namespace to refer
  # to properties relating to the client in the _from parameter, providing
  # access to __node#. parameters.
  # @param self The playernsd::simulation::Simulation instance.
  # @param _from The client that the property relates/comes from.
  # @param prop The property name.
  def prop_substitution(self, _from, prop):
    if _from != 0 and prop.startswith("self."):
      return '__node' + str(_from) + '.' + prop[len('self.'):]
    for t,i in self.cidi.iteritems():
      if prop.startswith(t + '.'):
        return '__node' + str(i) + '.' + prop[len(t)+1:]
    return prop
  ## Getting a property value from the target executable.
  # @param self The playernsd::simulation::Simulation instance.
  # @param _from The client that asked this.
  # @param prop The property name.
  def prop_get(self, _from, prop):
    prop = self.prop_substitution(self.cidi[_from], prop)
    self.writer.prop_get(self.cidi[_from], prop)
  ## Setting a property value in the target executable.
  # @param self The playernsd::simulation::Simulation instance.
  # @param _from The client that asked this.
  # @param prop The property name.
  # @param val The property value.
  def prop_set(self, _from, prop, val):
    prop = self.prop_substitution(self.cidi[_from], prop)
    self.writer.prop_set(prop, val)
  ## Worker routine for simulation.
  # @param self The playernsd::simulation::Simulation instance.
  def run(self):
    while True:
      stuff = self.p.stdout.read(1)
      # If nothing read, terminate simulation thread.
      if stuff == None or len(stuff) == 0:
        break;
      cmd = unpack('B', stuff)[0]
      if cmd == MessageType.DISCONNECT:
        break
      elif cmd == MessageType.RECV:
        _from, to, length = unpack('<III', self.p.stdout.read(12))
        msg = self.p.stdout.read(length)
        # Ignore out of range clients
        log.debug("SIMRECV(%d->%d) %s" % (_from, to,
          msg.encode(sys.stdout.encoding,
            'backslashreplace').replace('\n', '\\n')))
        if to < self.cidn and _from < self.cidn:
          self.recv_callback(self.cidt[_from], self.cidt[to], msg)
      elif cmd == MessageType.PROPVAL:
        _from, length = unpack('<II', self.p.stdout.read(8))
        propval = self.p.stdout.read(length)
        prop, val = propval[:-1].split('\0')
        prop = self.prop_substitution(0, prop)
        self.prop_val_callback(self.cidt[_from], prop, val)
    self.stop()
  ## Stop the simulation
  # @param self The playernsd::simulation::Simulation instance.
  def stop(self):
    for i in range(1, self.cidn):
      self.writer.disconnect(i)
    self.writer.stop()
    self.writer.join()

# vim: ai:ts=2:sw=2:sts=2:
