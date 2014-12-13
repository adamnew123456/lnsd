"""
Ensures that the protocol handlers for the control protocol and the network
protocol work as expected.
"""
from collections import defaultdict
import socket
import threading
import traceback
import unittest

from lns import control_proto, reactor

# Change this to some port that is available on your machine, so that the
# control protocol handler and the control protocol client can communicate
TEST_CONTROL_PORT = 4097

# How long to check back with a threading.Event, so that the reactor runner
# thread can die within a reasonable time
RUNNER_CHECK_TIME = 2

def reactor_runner_thread(reactor, handler, event):
    "Steps a reactor, until the given event is triggered."
    while not event.isSet():
        reactor.poll(RUNNER_CHECK_TIME)
    handler.close()

class MockNetworkHandler:
    """
    A network handler created to test the control protocol handler, which
    provides static data for testing.
    """
    def __init__(self):
        self.host_ips = {'a': ['1.2.3.4', '9.10.11.12'], 
            'b': ['5.6.7.8'], 'c': ['13.14.15.16']}
        self.ip_hosts = {'1.2.3.4': 'a', '5.6.7.8': 'b', '9.10.11.12': 'a',
            '13.14.15.16': 'c'}

    def query_host(self, host):
        return self.host_ips.get(host, [])

    def query_ip(self, ip):
        return self.ip_hosts.get(ip, None)

    def get_host_ip_map(self):
        return self.host_ips.copy()

class TestNetworkProtocol(unittest.TestCase):
    def setUp(self):
        self.net_handler = MockNetworkHandler()
        self.reactor = reactor.Reactor()

        self.control_handler = control_proto.ProtocolHandler(self.net_handler, 
            self.reactor, port=TEST_CONTROL_PORT)
        self.control_handler.open()

        self.client = control_proto.ClientHandler(port=TEST_CONTROL_PORT)
        self.client.open()

        self.reactor_thread_quit_event = threading.Event()

        self.reactor_thread = threading.Thread(target=reactor_runner_thread,
            args=(self.reactor, self.control_handler, self.reactor_thread_quit_event))
        self.reactor_thread.setDaemon(True)
        self.reactor_thread.start()

    def tearDown(self):
        self.client.close()

        self.reactor_thread_quit_event.set()
        self.reactor_thread.join()

    def test_query_host(self):
        """
        Queries a known and an unknown host name.
        """
        self.assertEqual(self.client.get_ip('a'), ['1.2.3.4', '9.10.11.12'])
        self.assertEqual(self.client.get_ip('b'), ['5.6.7.8'])
        self.assertEqual(self.client.get_ip('nonexistent'), [])

    def test_query_ip(self):
        """
        Queries a known and an unknown IP address.
        """
        self.assertEqual(self.client.get_host('1.2.3.4'), 'a')
        self.assertEqual(self.client.get_host('5.6.7.8'), 'b')
        self.assertEqual(self.client.get_host('9.10.11.12'), 'a')
        self.assertEqual(self.client.get_host('13.14.15.16'), 'c')
        self.assertEqual(self.client.get_host('0.0.0.0'), None)

    def test_host_ip_mapping(self):
        """
        Queries the mapping from hostnames to IP addresses.
        """
        self.assertEqual(self.client.get_host_ip_mapping(), 
            {'a': ['1.2.3.4', '9.10.11.12'], 'b': ['5.6.7.8'], 'c': ['13.14.15.16']})

if __name__ == '__main__':
    unittest.main()
