"""
Ensures that the protocol manager can encode and decode messages circularly, so
that a message which is encoded and decoded is equal to the original message.
"""
import io
import unittest

from lns import control_proto, net_proto

class NetworkProtocol(unittest.TestCase):
    def roundtrip(self, message):
        output = message.serialize()

        output_message = net_proto.Announce.unserialize(output)
        self.assertEqual(message, output_message)

    def test_announce(self):
        self.roundtrip(net_proto.Announce('this is a hostname'))

        # This is bad because it is too long for the protocol
        with self.assertRaises(ValueError):
            self.roundtrip(net_proto.Announce((net_proto.PACKET_SIZE * 2) * 'x'))

        # This is bad because it contains unprintable characters
        with self.assertRaises(ValueError):
            self.roundtrip(net_proto.Announce('unprintables: \x7f\x00'))

        # This is bad because empty hosts are not allowed
        with self.assertRaises(ValueError):
            self.roundtrip(net_proto.Announce(''))

class ControlProtocol(unittest.TestCase):
    BAD_HOSTNAMES = [
        # Too long, since the max length is the size of the packet minus 1
        (net_proto.PACKET_SIZE * 2) * 'x',
        # Only printable ASCII is allowed in hostnames
        'unprintables: \7f\x00',
        # Hostnames must be non-empty
        ''
    ]

    BAD_IPS = [
        '255.256.257.258',
        '1.2.3',
        '1.2.3.4.5'
    ]

    def roundtrip(self, message):
        output = message.serialize()

        stream = io.BytesIO(output)
        json = control_proto.get_length_encoded_json(stream)

        message_class = control_proto.get_message_class(json)
        self.assertTrue(message_class.parses(json))
        
        output_message = message_class.unserialize(json)
        self.assertEqual(message, output_message)

    def test_host(self):
        self.roundtrip(control_proto.Host('foo'))

        for bad_host in self.BAD_HOSTNAMES:
            with self.assertRaises(ValueError):
                self.roundtrip(control_proto.Host(bad_host))

    def test_ip(self):
        self.roundtrip(control_proto.IP(['1.2.3.4', '5.6.7.8']))

        for bad_ip in self.BAD_IPS:
            with self.assertRaises(ValueError):
                self.roundtrip(control_proto.IP([bad_ip]))

    def test_get_all(self):
        self.roundtrip(control_proto.GetAll())

    def test_name_ip_mapping(self):
        self.roundtrip(control_proto.NameIPMapping({}))
        self.roundtrip(control_proto.NameIPMapping({
            'a': ['1.2.3.4', '9.10.11.12'], 'b': ['5.6.7.8']}))

        for bad_host in self.BAD_HOSTNAMES:
            with self.assertRaises(ValueError):
                self.roundtrip(control_proto.NameIPMapping({bad_host: ['1.2.3.4']}))

        for bad_ip in self.BAD_IPS:
            with self.assertRaises(ValueError):
                self.roundtrip(control_proto.NameIPMapping({'a': [bad_ip]}))

if __name__ == '__main__':
    unittest.main()
