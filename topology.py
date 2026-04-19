from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.topo import Topo
from mininet.cli import CLI
from mininet.log import setLogLevel

class AccessControlTopo(Topo):
    def build(self):
        # One switch
        s1 = self.addSwitch('s1')

        # Four hosts - h1 and h2 are whitelisted, h3 and h4 are blocked
        h1 = self.addHost('h1', mac='00:00:00:00:00:01', ip='10.0.0.1/24')
        h2 = self.addHost('h2', mac='00:00:00:00:00:02', ip='10.0.0.2/24')
        h3 = self.addHost('h3', mac='00:00:00:00:00:03', ip='10.0.0.3/24')
        h4 = self.addHost('h4', mac='00:00:00:00:00:04', ip='10.0.0.4/24')

        # Connect all hosts to switch
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)
        self.addLink(h4, s1)

def run():
    setLogLevel('info')
    topo = AccessControlTopo()
    net = Mininet(topo=topo, controller=RemoteController('c0', ip='127.0.0.1', port=6633))
    net.start()
    CLI(net)
    net.stop()

if __name__ == '__main__':
    run()
