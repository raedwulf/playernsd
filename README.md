PlayerNSD v0.0.1
================

Introduction
------------

This is a player network simulator daemon that works in conjunction with nsdnet,
which allows messages to be sent between robots in [Player][1] and supports
the use of network simulation scripts and external simulators such as [ns3][2].
Please see COPYING for license information.

  [1]: http://playerstage.sourceforge.net/index.php?src=player
  [2]: http://www.nsnam.org/

Dependencies
------------

* [Python][3] (tested with python 2.5 and python 2.7)
* [Player][1] (tested with 3.0.2)
* [CMake][2] (tested with 2.8.1)

 [2]: http://www.cmake.org/
 [3]: http://www.python.org/

Running
-------

This daemon can be run by using the wrapper playernsd script:
	$ ./playernsd

More options can be found by executing:
	$ ./playernsd --help

For example, to run an example wifi simulator using NS3 as a backend:
	$ ./playernsd -o "verbose=true" ../nssim/build/wifisim

Or for a simple script, that provides line of sight communication (for use
with Stage maps):
	$ ./playernsd -o image=pathto/cave.png,width=25,height=25 -v examples/lineofsight.py

These paths assume you are running directly from the repository.
