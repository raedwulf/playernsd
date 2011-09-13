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

##@file passthrough.py
# The simulation class that does nothing but pass messages through.

import sys
import thread
import logging
import time
from Queue import Queue
from threading import Thread
from struct import *

log = logging.getLogger('playernsd')

## Simulation thread for controlling the simulation executable.
class Simulation(Thread):
  ## Initialise this class.
  # @param self The simulation::Simulation instance.
  # @param args The.extra arguments provided to run the simulation script.
  # @param recv_callback The callback to call when a message is recevied.
  # @param prop_val_callback The callback to call when a property
  #        value is received.
  def __init__(self, args, recv_callback, prop_val_callback):
    self.recv_callback = recv_callback
    self.prop_val_callback = prop_val_callback
    self.clients = []
    self.properties = {}
    Thread.__init__(self)
  ## Add new client.
  #
  # This typically can only added up to some application defined limit of
  # maximum clients.
  # @param self The simulation::Simulation instance.
  # @param clientid Client ID of client added.
  def new_client(self, clientid):
    self.clients.append(clientid)
  ## Send a message simulated.
  # @param self The simulation::Simulation instance.
  # @param _from The client that the message comes from.
  # @param to The client that the messagesa is being sent to.
  # @param msg The message to be sent.
  def send(self, _from, to, message):
    # Need to handle special case of broadcasting to individual clients.
    if to == '__broadcast__':
      for c in self.clients:
        if c != _from:
          self.recv_callback(_from, c, message);
    else:
      # Direct to a single client, message.
      self.recv_callback(_from, to, message);
  ## Getting a property value from the target executable.
  # @param self The simulation::Simulation instance.
  # @param _from The client that asked this.
  # @param prop The property name.
  def prop_get(self, _from, prop):
    # Replace 'self'
    if prop.startswith('self.'):
      p = _from + '.' + prop[len('self.'):]
    else:
      p = prop
    # Split property into parts (using '.' separator).
    parts = p.split('.')
    if parts[0] in self.clients:
      if parts[1] == 'index':
        self.prop_val_callback(_from, prop, self.clients.index(parts[0]) + 1)
        return
    # Check properties dictionary for other stored information.
    if p in self.properties:
      self.prop_val_callback(_from, prop, self.properties[p])
      return
    # Unhandled, default to empty string.
    self.prop_val_callback(_from, prop, '')
  ## Setting a property value in the target executable.
  # @param self The simulation::Simulation instance.
  # @param _from The client that asked this.
  # @param prop The property name.
  # @param val The property value.
  def prop_set(self, _from, prop, val):
    # Replace 'self'
    if prop.startswith('self.'):
      p = _from + '.' + prop[len('self.'):]
    else:
      p = prop
    self.properties[p] = val
  ## Worker routine for simulation.
  # @param self The simulation::Simulation instance.
  def run(self):
    # Worker routine doesn't need to do much because we're just pass through.
    self.running = True
    while self.running:
      time.sleep(1)
    self.stop()
  ## Stop the simulation
  # @param self The simulation::Simulation instance.
  def stop(self):
    if not self.running:
      self.running = False

# vim: ai:ts=2:sw=2:sts=2:
