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
import Image
from Queue import Queue
from threading import Thread
from struct import *
from math import *

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
    self.positions = {}
    self.properties = {}
    self.image = self.width = self.height = None
    for a in args[1:]:
      p,v = a.split('=')
      if p == 'image':
        self.image = Image.open(v)
        self.map = self.image.load()
      elif p == 'width':
        self.width = float(v)
        self.scale_x =  float(self.image.size[0]) / float(self.width)
      elif p == 'height':
        self.height = float(v)
        self.scale_y =  float(self.image.size[1]) / float(self.height)
      else:
        raise Exception('lineofsight script doesn\'t understand argument '+ p)
    if self.image == None or self.width == None or self.height == None:
      raise Exception('lineofsight needs arguments -o image=img,width=#,height=#')
    log.debug('SIMINIT: imagesize: (%f, %f), scaledsize: (%f, %f)' % (self.image.size[0], self.image.size[1], self.width, self.height))
    Thread.__init__(self)
  ## Add new client.
  #
  # This typically can only added up to some application defined limit of
  # maximum clients.
  # @param self The simulation::Simulation instance.
  # @param clientid Client ID of client added.
  def new_client(self, clientid):
    self.clients.append(clientid)
    # We need to have at least an initial position.
    #self.positions[clientid] = (0, 0)
  ## Tracing a line to check for intersections.
  #
  # This is for detecting if the robot can send a message (or not).
  # Algorithm from http://playtechs.blogspot.com/2007/03/raytracing-on-grid.html
  # @param p0 Source point.
  # @param p1 Destination point.
  def trace(self, p0, p1):
    print 'trace', str(p0), str(p1)
    x0 = p0[0] * self.scale_x + self.image.size[0] / 2
    y0 = self.image.size[1]/2 - p0[1] * self.scale_y
    x1 = p1[0] * self.scale_x + self.image.size[0] / 2
    y1 = self.image.size[1]/2 - p1[1] * self.scale_y
    print 'trace', x0, y0, x1, y1

    if x0 < 0 or x0 >= self.image.size[0] or y0 < 0 or y0 >= self.image.size[1]:
      return None
    if x1 < 0 or x1 >= self.image.size[0] or y1 < 0 or y1 >= self.image.size[1]:
      return None

    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x = int(floor(x0))
    y = int(floor(y0))
    n = 1
    walls = []

    if dx == 0:
      x_inc = 0
      error = float("inf")
    elif x1 > x0:
      x_inc = 1
      n += int(floor(x1)) - x
      error = (floor(x0) + 1 - x0) * dy
    else:
      x_inc = -1
      n += x - int(floor(x1))
      error = (x0 - floor(x0)) * dy

    if dy == 0:
      y_inc = 0
      error -= float("inf")
    elif y1 > y0:
      y_inc = 1
      n += int(floor(y1)) - y
      error -= (floor(y0) + 1 - y0) * dx
    else:
      y_inc = -1
      n += y - int(floor(y1))
      error -= (y0 - floor(y0)) * dx

    for n in range(n, 0, -1):
      # if is a wall
      #print x, y, self.map[x, y]
      if self.map[x, y] == 0 or self.map[x, y] == (0, 0) or self.map[x, y] == (0, 0, 0) or self.map[x, y] == (0, 0, 0, 0) or self.map[x, y] == (0, 0, 0, 255):
        walls.append((x, y))

      if error > 0:
        y += y_inc
        error -= dx
      else:
        x += x_inc
        error += dy
    return walls
  ## Send a message with line of sight taken into account
  # @param self The simulation::Simulation instance.
  # @param _from The client that the message comes from.
  # @param to The client that the messagesa is being sent to.
  # @param msg The message to be sent.
  def trace_send(self, _from, to, message):
    # Can't send if one of the client robots is nowhere.
    if _from not in self.positions or to not in self.positions:
      return
    # Can you see the target? Trace walls...
    walls = self.trace(self.positions[_from], self.positions[to])
    if walls == []:
      # Direct to a single client, message.
      self.recv_callback(_from, to, message);
    elif walls == None:
      log.debug('SIMSEND: Trace failed.')
    else:
      log.debug('SIMSEND: Sent message from %s to %s but wall(s) detected at %s' % (_from, to, str(walls)))
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
          self.trace_send(_from, c, message);
    else:
      self.trace_send(_from, to, message)
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
    if p.find('.') != -1:
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
    # Handle position changes as they come in
    if p.find('.') != -1:
      c, c1 = p.split('.')
      if c1 == 'position':
        self.positions[c] = tuple(map(float, self.properties[p].split(' ')))
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
