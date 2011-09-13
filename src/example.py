import ns.applications
import ns.core
import ns.csma
import ns.internet
import ns.network
from threading import Thread

class Simulator(Thread):
  def __init__(self, callback):
    phyMode = "DsssRate1Mbps"
    rss = -80
    interval = 0.01
    maxClients = 10

    ns.core.GlobalValue.Bind("SimulatorImplementationType",
      ns.core.StringValue("ns3::RealtimeSimulatorImpl"))

    # convert to time object
    interPacketInterval = ns.core.Seconds(interval)

    # disable fragmentation for frames below 2200 bytes
    ns.core.Config.SetDefault("ns3::WifiRemoteStationManager::FragmentationThreshold", ns.core.StringValue("2200"));
    # turn off RTS/CTS for frames below 2200 bytes
    ns.core.Config.SetDefault("ns3::WifiRemoteStationManager::RtsCtsThreshold", ns.core.StringValue("2200"));
    # Fix non-unicast data rate to be the same as that of unicast
    ns.core.Config.SetDefault("ns3::WifiRemoteStationManager::NonUnicastMode", ns.core.StringValue(phyMode));

    # create nodes
    c = ns.network.NodeContainer()
    c.Create(maxClients)

    # the below set of helpers will help us to put together the wifi NICs we want.
    wifi = ns.wifi.WifiHelper.Default()
    wifi.EnableLogComponents() # turn on all wifi logging
    wifi.SetStandard(ns.wifi.WIFI_PHY_STANDARD_80211b)

    wifiPhy = ns.wifi.YansWifiPhyHelper.Default()
    # this is the one parameter that matters when using FixedRssLossModel
    # set it to zero; otherwise gain will be added
    wifiPhy.Set("RxGain", ns.core.DoubleValue(0))

    wifiChannel = ns.wifi.YansWifiChannelHelper.Default()
    wifiChannel.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    # the below FixedRssLossModel will cause the rss to be fixed regardless
    # of the distance between the two stations, and the transmit power.
    wifiChannel.AddPropagationLoss("ns3::FixedRssLossModel", "Rss", ns.core.DoubleValue(rss))
    wifiPhy.SetChannel(wifiChannel.Create())


    # add a non-QoS upper mac, and disable rate control
    wifiMac = ns.wifi.NqosWifiMacHelper.Default()
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager", "DataMode", ns.core.StringValue(phyMode),
      "ControlMode", ns.core.StringValue(phyMode))

    # set it to adhoc mode
    wifiMac.SetType("ns3::AdhocWifiMac")
    devices = wifi.Install(wifiPhy, wifiMac, c)

    # note that with FixedRssLossModel, the positions below are not
    # used for received signal strength.
    mobility = ns.mobility.MobilityHelper()
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel")
    mobility.Install(ap)

    internet = ns.internet.InternetStackHelper()
    internet.Install(c)

    ipv4 = ns.internet.Ipv4AddressHelper()
    ipv4.SetBase("10.1.1.0", "255.255.255.0")
    ifc = ipv4.Assign(devices)

    #ns.core.Simulator.Schedule(ns.core.Seconds(1.0), AdvancePosition, ap.Get(0))
    i = 0
    self.cs = []
    self.sc = {}
    self.ai = []
    self.cidi = {'__broadcast__':0}
    self.cidt = ['__broadcast__']
    self.cidn = 1

    def recv_packet_cb(socket):
      print 'RAWR'
      # TODO: This must be broken
      # get the packet
      packet = socket.Recv()
      data = packet.CopyData(packet.GetSize())
      # for compatibility we must transform the packet into raw data
      self.callback(self.sc[socket], data)

    tid = ns.core.TypeID.LookupByName("ns3::UdpSocketFactory")
    for c in range(1, maxClients+1):
      socketAddress = ns.network.InetSocketAddress(ns.network.Ipv4Address("10.10.10." + str(i), 12254))
      self.cs.append(ns.network.Socket.CreateSocket(stas.Get(i), tid))
      self.cs[c].SetAllowBroadcast(True)
      self.cs[c].Bind(socketAddress)
      self.cs[c].SetRecvCallback(recv_packet_cb)
      self.sc[self.cs[c]] = c
      self.ai.append(socketAddress)

    # tracing
    wifiPhy.EnablePcap("example", devices)

    # schedule messages to be sent
    def generate_traffic(pktInterval):
      self.cs[0].SendTo("Hello World", 12, 0, self.ai[1])
      ns.core.Simulator.Schedule(pktInterval, generate_traffic, pktInterval)
    ns.core.Simulator.Schedule(ns.core.Seconds(0.1), generate_traffic, interPacketInterval)

  def send(clientid, message):
    pass

  def new_client(self, clientid):
    self.cidi[clientid] = self.cidn
    self.cidt.append(clientid)
    self.cidn += 1

  def prop_get(self, _from, prop):
    return 'apples'

  def prop_set(self, _from, prop, val):
    pass

  def run(self):
    #ns.core.Simulator.Stop(ns.core.Seconds(20))
    ns.core.Simulator.Run()
    ns.core.Simulator.Destroy()

