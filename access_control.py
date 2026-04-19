from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet

class AccessControlSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # Whitelist: only these MACs can send/receive traffic
    WHITELIST = {
        '00:00:00:00:00:01',  # h1
        '00:00:00:00:00:02',  # h2
    }

    def __init__(self, *args, **kwargs):
        super(AccessControlSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}  # learning table

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Install a table-miss flow to send unmatched packets to controller."""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Table-miss: send to controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, priority=0, match=match, actions=actions)

    def add_flow(self, datapath, priority, match, actions, idle=0):
        """Helper to install a flow rule on the switch."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                idle_timeout=idle, match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """Handle packets sent to controller. Apply whitelist policy."""
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None:
            return

        src = eth.src
        dst = eth.dst
        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("Packet in dpid=%s src=%s dst=%s in_port=%s", dpid, src, dst, in_port)

        # DENY: drop if source is not whitelisted
        if src not in self.WHITELIST:
            self.logger.warning("BLOCKED: src=%s is not in whitelist. Dropping.", src)
            # Install a drop rule for this source MAC (high priority)
            match = parser.OFPMatch(eth_src=src)
            self.add_flow(datapath, priority=10, match=match, actions=[], idle=30)
            return

        # DENY: drop if destination is not whitelisted (and not broadcast)
        if dst != 'ff:ff:ff:ff:ff:ff' and dst not in self.WHITELIST:
            self.logger.warning("BLOCKED: dst=%s is not in whitelist. Dropping.", dst)
            return

        # ALLOW: learn source port
        self.mac_to_port[dpid][src] = in_port

        # Decide output port
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Install a flow rule so future packets don't hit controller
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_src=src, eth_dst=dst)
            self.add_flow(datapath, priority=5, match=match, actions=actions, idle=60)

        # Send current packet
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions,
                                  data=msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None)
        datapath.send_msg(out)
