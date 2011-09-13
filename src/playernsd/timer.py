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

##@file timer.py
# The timer class containing playernsd::timer::ResettableTimer 
# and playernsd::timer::PeriodicTimer.
import threading

## Resettable timer class
#
# A timer that allows the time to be reset in the callback function.
# Original implementation from http://goo.gl/tAzYx
class ResettableTimer(threading.Thread):
  ## Constructor to create the timer from an interval and function.
  def __init__(self, interval, function, args=[], kwargs={}):
    threading.Thread.__init__(self)
    self.interval = interval
    self.function = function
    self.args = args
    self.kwargs = kwargs
    self.finished = threading.Event()
    self.resetted = True
  ## Cancel the timer.
  def cancel(self):
    self.finished.set()
  ## Run the timer at the set period and call the callback function.
  def run(self):
    while self.resetted:
      self.resetted = False
      self.finished.wait(self.interval)
      if not self.finished.isSet():
        self.function(*self.args, **self.kwargs)
    self.finished.set()
  ## Reset the timer, so it does not stop.
  def reset(self, interval=None):
    if interval:
      self.interval = interval
    self.resetted = True
    self.finished.set()
    self.finished.clear()

## Periodic timer class
#
# A timer that has a callback that is called at specific intervals.
class PeriodicTimer(ResettableTimer):
  ## Constructor to create the timer from an interval and function
  def __init__(self, interval, function, args=[], kwargs={}):
    self.__terminate=False
    self.__user_callback=function
    ResettableTimer.__init__(self, interval, self.callback,
      [self, args], kwargs)
  ## The callback function that trigger's the user callback at set period
  # as well as reset the timer automatically when the period finishes.
  def callback(self, args, kwargs):
    if self:
      self.__user_callback(args, kwargs)
      if not self.__terminate:
        self.reset()
  ## Cancels the periodic timer, so it no longer fires the callback.
  def cancel(self):
    self.__terminate=True
