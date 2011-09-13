#!/usr/bin/env python
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

## @file __init__.py
# @brief The NS3 daemon for player.
# @author Tai Chi Minh Ralph Eastwood <tcme500@cs.york.ac.uk>
# @author University of York
# @date 2011

## @namespace playernsd
#This is the main module which provides the interface
#between ns3 and player/stage.

## @mainpage playernsd
# @brief The NS3 daemon for player.
# @author Tai Chi Minh Ralph Eastwood <tcme500@cs.york.ac.uk>
# @author University of York
# @date 2011
#
# @section sec_details Implementation Details
#
#Details for the protocol can be found @ref page_protocol "here".
#

## @page page_protocol Protocol for communication
#
# @section sec_protocol Protocol for communication
#
# @subsection subsec_server_messages Server messages
# @li @b greetings IPADDRESS playernsd VERSION\\n
# @li @b registered
# @li @b pong\\n
# @li @b ping\\n
# @li @b error message\\n
# @li @b msgtext src\\nMESSAGE\\n
# @li @b msgbin src length\\nBINARYDATA
# @li @b propval var VALUE\n
#
# @subsection subsec_client_messages Client messages
# @li @b greetings CLIENTID playernsd VERSION\\n
# @li @b ping\\n
# @li @b pong\\n
# @li @b error message\\n
# @li @b msgtext [dest]\\nMESSAGE\\n
# @li @b msgbin [dest] length\\nBINARYDATA
# @li @b propget var\\n
# @li @b propset var VALUE\\n

import SocketServer
import socket
import time
import threading
import optparse
import sys
import logging
import os
import shlex
import imp
from playernsd.timer import PeriodicTimer
from playernsd.remoteclient import RemoteClient

# Global config variables
## Name of daemon
NAME = "playernsd"
## Version of playernsd protocol
VERSION = "0001"
__version__ = "0.0.1"
## IP to listen on
IP = ''
## Port to listen on
PORT = 9999
## Logfile name (playernsd.log is default)
LOGFILE = NAME + '.log'
## Verbosity level (1 is default)
VERBOSE = 1
## Maximum number of bytes to send (from client) (4096 is default)
MAX_SEND = 4096
## Maximum number of bytes to read (4096+64 is default)
MAX_READ = MAX_SEND + 64
## The timeout before a ping, i.e. the interval the client manager checks
CLIENT_TIMEOUT = 1.0
## The minimum number of pings missed before the client is disconnected
# unless there is an error on the socket, in which case, it is disconnected
# immediately.
MISSED_PING = 3

## Format for logging messages
LOG_FORMAT = '%(asctime)-15s %(levelname)-6s: %(message)s'

## Globals
properties = {}

## Get the value for a property.
# @param key The key of the property to get the value for.
def propget(key):
  if key in properties:
    return properties[key]
  else: # Ask ns3
    return None
## Set the value for a property.
# @param key The key of the property to get the value for.
def propset(key, value):
  if key in properties:
    properties[key] = value
  else: # Ask ns3
    pass

## The client manager class for handling client connections.
#
# The client manager class periodically checks clients by pinging them
# and waiting for a pong response.  Clients that fail to respond, will
# be discarded.  It also provides routines for sending and receiving 
# messages.
class ClientManager():
  ## Class constructor
  # @param self The instance of playernsd::ClientManager.
  # @param timeout The number of seconds for a timeout.
  # @param missed_ping The number of missed pings allowed before a disconnect.
  def __init__(self, timeout, missed_ping, simulation):
    self.__client_lock = threading.Lock()
    self.__timed_out_lock = threading.Lock()
    self.__clients = {}
    self.__clientids = {}
    self.__timed_out = []
    self.__ping_pong = {}
    self.__t = PeriodicTimer(timeout, self.__timeout_check, [self])
    ## The number of missed pings allowed
    self.missed_ping = missed_ping
    self.__sim = simulation
    self.__t.daemon = True
  ## Start the timeout poller
  # @param self The instance of playernsd::ClientManager.
  def start(self):
    self.__t.start()
  ## Stop the timeout poller
  # @param self The instance of playernsd::ClientManager.
  def stop(self):
    self.__t.cancel()
  ## Add a client that should be polled by the timeout poller
  # @param self The instance of playernsd::ClientManager.
  # @param address The address of the client.
  # @param client The associated playernsd:RemoteClient object.
  def add_client(self, address, client):
    with self.__client_lock:
      self.__clients[address] = RemoteClient(None, address, None, client)
      self.__ping_pong[address] = 1
  ## Register a client with name and protocol version.
  # @param name The name of the client.
  # @param address The addres sof the client.
  def register_client(self, address, name, version):
    self.__clients[address].name = name
    self.__clients[address].version = version
    self.__clientids[name] = self.__clients[address]
    if simulation:
      simulation.new_client(name)
  ## Check if the address is handled by the client manager.
  # @param identifier The identifier to refer uniquely to a client.
  def has_client(self, identifier):
    if isinstance(identifier, str):
      return identifier in self.__clientids
    else:
      return identifier in self.__clients
  ## Check if the address is already registered in the client manager.
  # @param identifier The identifier to refer uniquely to a client.
  def is_registered(self, identifier):
    if isinstance(identifier, str):
      return identifier in self.__clientids
    else:
      return identifier in self.__clients and self.__clients[identifier].name != None
  ## Get a RemoteClient object when identified by address or id.
  # @param identifier The identifier to refer uniquely to a client.
  def get_client(self, identifier):
    if isinstance(identifier, str):
      return self.__clientids[identifier]
    else:
      return self.__clients[identifier]
  ## Remove a client that is polled by the timeout poller.
  # @param self The instance of playernsd::ClientManager.
  # @param address The address of the client.
  def remove_client(self, address):
    with self.__client_lock:
      if self.__clients[address].name in self.__clientids:
        del self.__clientids[self.__clients[address].name]
      del self.__clients[address]
  ## Get a list of client ids.
  def get_clientid_list(self):
    l = []
    for v in self.__clients.itervalues():
      l.append(v.name)
    return l
  ## Indicate that a particular client has replied to a ping.
  # @param self The instance of playernsd::ClientManager.
  # @param address The address of the client.
  def pong(self, address):
    self.__ping_pong[address] = 0
  ## Check if a particular client has timed out.
  # @param self The instance of playernsd::ClientManager.
  # @param address The address of the client.
  # @return Boolean return indicating whether the client has timed out.
  def is_timed_out(self, address):
    return address in self.__timed_out or \
      self.__ping_pong[address] < -self.missed_ping
  ## Send a message to a client.
  #
  # This is a wrapper function to send a message to a client.
  # By default, this sends the message to the client that invoked the request,
  # but with the parameters @a s (the target socket) and
  # @a ca (the target client address), any client can be messaged.
  # @param self The playernsd::ClientManager instance.
  # @param msg The message to be sent.
  # @param s The socket to send the message to.
  # @param ca The client address to send the message to.
  def send(self, msg, s, ca):
    if VERBOSE > 1:
      self.log(ca, 'SEND(' + str(len(msg)) + ')', msg)
    # read the type of message, and see if the message should be
    # simulated
    command = msg.split(' ')
    if simulation and (command[0] == 'msgtext' or command[0] == 'msgbin'):
      self.__sim.send(command[1], self.__clientids(ca),
        msg[msg.find('\n')+1:])
    else:
      s.send(msg)
  ## Get a property from the simulation
  #
  # This function requests a value from the simulation.
  # @param self The playernsd::ClientManager instance.
  # @param ca The client address that this request comes from.
  # @param prop The name of the property.
  def prop_get_sim(self, prop, ca):
    if self.__sim:
      cid = self.__clients[ca].name
      self.__sim.prop_get(cid, prop)
    else:
      self.__clients[ca].socket.send('propval ' + prop + ' ' + '\n')
  ## Set a property in the simulation
  #
  # This function sets a value from the simulation.
  # @param self The playernsd::ClientManager instance.
  # @param _from The client address that this request comes from.
  # @param prop The name of the property.
  # @param val The value of the property.
  def prop_set_sim(self, prop, val, ca):
    if self.__sim:
      cid = self.__clients[ca].name
      self.__sim.prop_set(cid, prop, val)
  ## Broadcast a message to all clients.
  #
  # This is a wrapper function to broadcast a message to all clients.
  # @param self The playernsd::ClientManager instance.
  # @param msg The message to be sent to all clients.
  def broadcast(self, msg):
    if simulation:
      command = msg.split(' ')
      self.__sim.send(command[1], '__broadcast__',
        msg[msg.find('\n')+1:])
    else:
      for v in self.__clients.itervalues():
        self.send(msg, v.socket, v.address)
  ## Receive a message from a client.
  #
  # This is a wrapper function to receive a message from a client and
  # logs it.
  # @param self The playernsd::ClientManager instance.
  # @param s The socket to send the message to.
  # @param ca The client address to send the message to.
  # @return The message received from the client.
  def recv(self, s, ca):
    data = s.recv(MAX_READ)
    if VERBOSE > 1:
      self.log(ca, 'RECV(' + str(len(data)) + ')', data)
    return data
  ## Receive a message from the simulation.
  def recv_sim(self, _from, to, msg):
    self.__clientids[to].socket.send('msgbin ' + _from + ' ' + str(len(msg)) + '\n' + msg)
  ## Receive a property value from the simulation.
  def prop_val_sim(self, _from, prop, val):
    #if val == "":
      #self.send('error propnotexist\n') # TODO: Handle empty strings separately?
    #else:
    self.__clientids[_from].socket.send('propval ' + prop + ' ' + str(val) + '\n')
  ## Create a log message.
  #
  # This is used internally to log sent and received messages.
  # This is typically only called when --verbose is passed to the daemon.
  # @param self The playernsd::ClientManager instance.
  # @param ca Client address related to log message.
  # @param tag Tag indicating the log level.
  # @param msg The message to be logged.
  def log(self, ca, tag, msg):
    if len(msg):
      logmsg = tag + ': ' + msg.encode(sys.stdout.encoding,
        'backslashreplace').replace('\n', '\\n')
      log.debug(self.get_id(ca) + ' ' + logmsg)
  ## Get id of client or else return '__unregistered'
  def get_id(self, ca):
    if ca in self.__clients and self.__clients[ca].name != None:
      return '[' + str(ca) + ', ' + self.__clients[ca].name + ']'
    else:
      return '[' + str(ca) + ', __unregistered]'
  # Callback function that periodically checks all clients to see whether
  # they are still responding.
  # @param args Additional arguments.
  # @param args Additional keyword arguments.
  def __timeout_check(self, args, kwargs):
    with self.__client_lock:
      for k,v in self.__clients.iteritems():
        try:
          self.send('ping\n', v.socket, k)
          self.__ping_pong[k] -= 1
          if self.__ping_pong[k] < -self.missed_ping:
            log.warn(str(k) + ' has missed at least ' +
              str(-self.__ping_pong[k]+1) + ' pings, closing connection')
            self.send('error missedping\n', v.socket, k)
            v.socket.shutdown(1)
        except socket.error, msg:
          if not self.is_timed_out(k):
            self.__timed_out.append(k)
            log.warn('Lost connection to ' + str(k) + ' ' + str(msg))
  ## Stop the client manager thread
  #
  # This is used to gracefully close the client manager and simulation threads.
  # @param self The playernsd::ClientManager instance.
  def stop(self):
    log.info('Client manager closing down...');
    if self.__sim:
      log.info('Stopping simulator...');
      self.__sim.stop()
      log.info('Simulator stopped...');
    log.info('Stopping timeout checker...');
    self.__t.cancel()
    log.info('Timeout checker stopped...');


## Request state enumeration (Internal)
class RequestState:
  COMMAND = 0
  MSGTEXT = 1
  MSGBIN = 2

## The TCP request handler class interacts with clients.
#
# The TCP request handler class deals with all the connections, messages 
# received and replies with the clients.
class TCPRequestHandler(SocketServer.BaseRequestHandler):
  ## Send a message to a client.
  #
  # This is a wrapper function to send a message to a client.
  # By default, this sends the message to the client that invoked the request,
  # but with the parameters @a s (the target socket) and
  # @a ca (the target client address), any client can be messaged.
  # @param self The playernsd::TCPRequestHandler instance.
  # @param msg The message to be sent.
  # @param s The socket to send the message to.
  # @param ca The client address to send the message to.
  def send(self, msg, s=None, ca=None):
    if not s:
      s = self.request
    if not ca:
      ca = self.client_address
    client_manager.send(msg, s, ca)
  ## Broadcast a message to all clients.
  #
  # This is a wrapper function to broadcast a message to all clients.
  # @param self The playernsd::TCPRequestHandler instance.
  # @param msg The message to be sent to all clients.
  def broadcast(self, msg):
    client_manager.broadcast(msg)
  ## Receive a message from a client.
  #
  # This is a wrapper function to receive a message from a client and
  # logs it.
  # @param self The playernsd::TCPRequestHandler instance.
  # @param s The socket to send the message to.
  # @param ca The client address to send the message to.
  # @return The message received from the client.
  def recv(self, s=None, ca=None):
    if not s:
      s = self.request
    if not ca:
      ca = self.client_address
    return client_manager.recv(s, ca)
  ## Setup a connection with a client.
  #
  # This is called whenever a new client connects.
  # @param self The playernsd::TCPRequestHandler instance.
  def setup(self):
    ca = self.client_address
    log.info(client_manager.get_id(ca) + ' Connected!')
    self.send('greetings ' + ca[0] + ' ' + NAME + ' ' + VERSION + '\n')
    client_manager.add_client(ca, self.request)
    self.__state = RequestState.COMMAND
  ## Function that handles all client requests.
  #
  # For a description of the protocol, please see \ref page_protocol "Protocol for communication".
  # @param self The playernsd::TCPRequestHandler instance.
  def handle(self):
    msgbin = ''
    msg_len = 0
    data = ''
    __state = RequestState.COMMAND
    lastlen = 0
    while True:
      try:
        # Shorthand for client address
        ca = self.client_address
        # Clear anything that has timed out
        if client_manager.is_timed_out(ca):
          return
        # Check state if we're currently reading binary msg
        if __state == RequestState.MSGBIN:
          if msg_len > len(data):
            data += self.recv()
          readlen = len(data)
          msgbin += data[:msg_len]
          data = data[msg_len:]
          msg_len -= readlen
          if msg_len <= 0:
            if msg_broadcast:
              self.broadcast('msgbin ' + client_manager.get_client(ca).name + ' ' +
                str(len(msgbin)) + '\n' + msgbin)
            else:
              self.send('msgbin ' + client_manager.get_client(ca).name + ' ' +
                str(len(msgbin)) + '\n' + msgbin, msg_cs, msg_ca)
            __state = RequestState.COMMAND
          continue
        elif __state == RequestState.MSGTEXT:
          # Look for new lines in current data
          nlpos = data.find('\n')
          if nlpos == -1:
            # None found, grab some new data
            data += self.recv()
            # Anything to do?
            if len(data) == 0:
              continue
            # Look for new lines in new data
            nlpos = data.find('\n')
            # None found: *shouldn't happen unless really slow connection*
            if nlpos == -1:
              # Warn about this:
              log.warn(client_manager.get_id(ca) + ' Data received for msgtext, but no newline.')
              continue
          # Get the message text
          msgtext = data[:nlpos]
          # Remove that from the data
          data = data[nlpos+1:]
          # Send the message off
          if msg_broadcast:
            self.broadcast('msgtext ' + client_manager.get_client(ca).name + '\n' + msgtext)
          else:
            self.send('msgtext ' + client_manager.get_client(ca).name + '\n' + msgtext, msg_cs, msg_ca)
          __state = RequestState.COMMAND
          continue
        elif __state == RequestState.COMMAND:
          # Look for new lines in current data
          nlpos = data.find('\n')
          if nlpos == -1:
            # None found, grab some new data
            data += self.recv()
            # Anything to do?
            if len(data) == 0:
              continue
            # Look for new lines in new data
            nlpos = data.find('\n')
            # None found: *shouldn't happen unless really slow connection*
            if nlpos == -1:
              # Warn about this:
              if lastlen != len(data):
                lastlen = len(data)
                log.warn(client_manager.get_id(ca) + ' Data received, but no commands.')
              continue
        # Parse one message out
        command = data[:nlpos].split(' ')
        # Remove that from the data
        data = data[nlpos+1:]
        # We don't need the command after we know what it is
        cmd = command.pop(0)
        if cmd == 'greetings':
          # check parameter count
          if len(command) < 3:
            self.send('error invalidparamcount\n')
            continue
          # store the client's id for the address
          cid = command.pop(0)
          if client_manager.is_registered(ca):
            # if already registered, don't register again (send error back)
            self.send('error alreadyregistered\n')
          elif client_manager.is_registered(cid):
            # if it already exists, this is a problem, send back error
            # and disconnect
            log.error(client_manager.get_id(ca) + ' tried to connect using id \'' + cid +
              '\' which is assigned to ' + client_manager.get_client(cid).name)
            # tell client that name is in use
            self.send('error clientidinuse\n')
          else:
            # add client to the list of clients & client ids & version
            log.info(client_manager.get_id(ca) + ' registered with name \'' + cid + '\'')
            if command[0] != NAME:
              log.error(client_manager.get_id(ca) + ' name of the client is ' + command[0])
              # terminate the connection
              return
            client_manager.register_client(ca, cid, command[1])
            self.send("registered\n")
        elif cmd == 'listclients':
          # list all the client ids
          clientslist = 'listclients '
          for name in client_manager.get_clientid_list():
            if name != None:
              clientslist += name + ' '
          self.send(clientslist + '\n')
        elif cmd == 'propget':
          # get a property value
          val = propget(command[0])
          if val != None:
            self.send('propval ' + command[0] + ' ' + val + '\n')
          else: # Ask NS3
            client_manager.prop_get_sim(command[0], self.client_address)
        elif cmd == 'propset':
          # set a property using a key & value
          # TODO: is ' '.join safe?
          key = command.pop(0)
          val = propget(key)
          if val != None:
            propset(key, ' '.join(command))
          else:
            client_manager.prop_set_sim(key, ' '.join(command), self.client_address)
        elif cmd == 'ping':
          self.send('pong\n')
        elif cmd == 'pong':
          client_manager.pong(ca)
        elif cmd == 'bye':
          return
        elif not client_manager.has_client(ca):
          # if client has not registered
          self.send('error notregistered\n')
        elif cmd == 'msgtext':
          if len(command) == 0: # zero param == broadcast
            # prepare to send message next loop iteration
            msg_broadcast = True
            __state = RequestState.MSGTEXT
          elif len(command) == 1: # two params == to a particular client
            # send a message to a client
            cid = command.pop(0)
            if client_manager.has_client(cid):
              _ca = client_manager.get_client(cid).address
              # prepare to send message next loop iteration
              msg_ca = client_manager.get_client(cid).address
              msg_cs = client_manager.get_client(_ca).socket
              msg_broadcast = False
              __state = RequestState.MSGTEXT
            else:
              self.send('error unknownclient\n')
          else: # else error that the param count is invalid
            self.send('error invalidparamcount\n')
        elif cmd == 'msgbin':
          if len(command) == 1: # one param == broadcast
            msglen = command.pop(0)
            if msglen.isdigit() or msglen > MAX_SEND:
              # check if all of the message is in the existing buffer
              msg_len = int(msglen)
              if len(data) >= msg_len:
                msgbin = data[:msg_len]
                data = data[msg_len:]
                self.broadcast('msgbin ' + client_manager.get_client(ca).name + ' ' +
                  msglen + '\n' + msgbin)
              else:
                # Receive the required data in next iteration
                msgbin = data
                msg_len -= len(data)
                data = ''
                msg_broadcast = True
                __state = RequestState.MSGBIN
            else:
              self.send('error invalidparam\n')
          elif len(command) == 2: # two params == to a particular client
            # send a binary message to a client
            cid = command.pop(0)
            if client_manager.has_client(cid):
              _ca = client_manager.get_client(cid).address
              _cs = client_manager.get_client(_ca).socket
              msglen = command.pop(0)
              if msglen.isdigit() or msglen > MAX_SEND:
                # check if all of the message is in the existing buffer
                msg_len = int(msglen)
                if len(data) >= msg_len:
                  msgbin = data[:msg_len]
                  data = data[msg_len:]
                  self.send('msgbin ' + client_manager.get_client(ca).name + ' ' + msglen +
                    '\n' + msgbin, _cs, _ca)
                else:
                  # Receive the required data in next iteration
                  msgbin = data
                  msg_len -= len(data)
                  msg_cs = _cs
                  msg_ca = _ca
                  msg_broadcast = False
                  __state = RequestState.MSGBIN
              else: # error that the parameter is invalid (expected integer)
                self.send('error invalidparam\n')
            else: # error that the client is unknown
              self.send('error unknownclient\n')
          else: # else error that the param count is invalid
            self.send('error invalidparamcount\n')
        else:
          log.warn(client_manager.get_id(ca) + ' Unknown command "' + cmd + '".')
          self.send('error unknowncmd\n')
      except socket.error, msg:
        log.error(msg)
        return
  ## Function that finalises communications with the client
  #
  # This will clear up references to disconnected clients and makes
  # sure that the playernsd::ClientManager instance
  # playernsd::client_manager no longer polls it.
  # @param self The playernsd::TCPRequestHandler instance.
  def finish(self):
    # Shorthand for client address
    ca = self.client_address
    log.info(client_manager.get_id(ca) + ' Disconnected!')
    # delete the items
    client_manager.remove_client(ca)

# server host is a tuple ('host', port)
if __name__ == "__main__":
  ## Instance of option parser to parse command line arguments passed
  parser = optparse.OptionParser(usage="usage: %prog [options] simulatorprogram")
  parser.add_option("-i", "--ip", type="string", dest="ip", default=IP,
                    help="listen on IP", metavar="IP")
  parser.add_option("-p", "--port", type="int",
                    dest="port", default=PORT,
                    help="don't print status messages to stdout")
  parser.add_option("-v", "--verbose", action="store_const", const=2, dest="verbose",
                    default=VERBOSE, help="verbose logging")
  parser.add_option("-q", "--quiet", action="store_const", const=0, dest="verbose",
                    default=VERBOSE, help="quiet logging")
  parser.add_option("-l", type="string", dest="logfile", default=LOGFILE,
                    help="specify logfile", metavar="FILE")
  parser.add_option("-o", type="string", dest="sim_options", default='',
                    help="options to simulation")
  parser.add_option("-m", "--environment-image", type="string", dest="envimage",
                    help="environment image for line-of-sight communication")
  (options, args) = parser.parse_args()
  # If args is specified, load the script file
  simulation = None
  if len(args) > 0:
    if os.path.exists(args[0]):
      # Get module extension
      module, extension = os.path.splitext(args[0])
      if options.sim_options.find(',') != -1:
        fullargs = options.sim_options.split(',')
      else:
        fullargs = []
      fullargs.insert(0, args[0])
      def recv_callback(_from, to, msg):
        client_manager.recv_sim(_from, to, msg)
      def prop_val_callback(_from, prop, val):
        client_manager.prop_val_sim(_from, prop, val)
      if extension == '.py':
        script = imp.load_source(module, args[0])
        simulation = script.Simulation(fullargs, recv_callback, prop_val_callback)
      else:
        # Run simulation with external binary
        from playernsd.simulation import Simulation
        simulation = Simulation(fullargs, recv_callback, prop_val_callback)
    else:
      print 'Cannot load script file ' + args[0] + '.'
      sys.exit(1)
  # Set the settings variables
  IP = options.ip
  PORT = options.port
  LOGFILE = options.logfile
  VERBOSE = options.verbose
  # Setup the logging facility
  ## The logging level
  loglevel = logging.DEBUG
  if VERBOSE == 0:
    loglevel = logging.ERROR
  elif VERBOSE == 1:
    loglevel = logging.INFO
  # Playernsd logging
  log = logging.getLogger('playernsd')
  # Additional debug levels (for formatting)
  # Default level
  log.setLevel(loglevel)
  # Stream handler
  formatter = logging.Formatter(LOG_FORMAT)
  hs = logging.StreamHandler()
  hs.setFormatter(formatter)
  hs.setLevel(loglevel)
  log.addHandler(hs)
  # Logfile handler
  hf = logging.FileHandler(LOGFILE)
  hf.setFormatter(formatter)
  hf.setLevel(loglevel)
  log.addHandler(hf)
  try:
    # Say what we're listening to & that we're verbose
    log.info('Listening on ' + IP + ':' + str(PORT) + '.')
    log.info('Verbosity=' + logging.getLevelName(loglevel) + ' logging' + '.')
    # Create the socket server
    SocketServer.TCPServer.allow_reuse_address = True
    server = SocketServer.ThreadingTCPServer((IP, PORT), TCPRequestHandler)
    # Start a thread with the server -- that thread will then start one
    # more thread for each request
    server_thread = threading.Thread(target=server.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.daemon = True
    server_thread.start()
    log.info('Server thread started.')
    # Start the simulation
    if simulation:
      simulation.daemon = True
      simulation.start()
    ## The client manager instance instantiated with the client timeout
    # and the missed ping count
    client_manager = ClientManager(CLIENT_TIMEOUT, MISSED_PING, simulation)
    client_manager.daemon = True
    client_manager.start()
    log.info('Client manager thread started.')
    # Main thread loop
    while True:
      time.sleep(0.1)
  except (KeyboardInterrupt, SystemExit):
    log.info('Received keyboard interrupt, quitting threads.\n')
    client_manager.stop()

# vim: ai:ts=2:sw=2:sts=2:
