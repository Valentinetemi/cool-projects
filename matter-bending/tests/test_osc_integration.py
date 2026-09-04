"""End-to-end check that OscSender actually puts well-formed bytes on the
wire -- the unit tests in test_osc_bridge.py only exercise build_messages()
and format_debug_line(), which never touch python-osc or a socket, so a
bug inside OscSender.send() itself (like a wrong constant name) can slip
past them. This test builds a real OscSender, sends a real HandState over
a real UDP socket to a listener on localhost, and decodes the bundle that
arrives.

Skipped automatically if python-osc isn't installed, since it's only a
runtime dependency (see requirements.txt), not needed to import
osc_bridge itself.
"""

import pathlib
import socket
import sys
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import osc_bridge as ob  # noqa: E402

try:
    from pythonosc.osc_bundle import OscBundle

    HAVE_PYTHON_OSC = True
except ImportError:
    HAVE_PYTHON_OSC = False


@unittest.skipUnless(HAVE_PYTHON_OSC, "python-osc not installed")
class OscSenderIntegrationTests(unittest.TestCase):
    def test_send_delivers_a_well_formed_bundle(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))  # OS-assigned free port, avoids clashing
        sock.settimeout(3)
        port = sock.getsockname()[1]

        received = []

        def listen():
            try:
                data, _ = sock.recvfrom(4096)
                received.append(data)
            except socket.timeout:
                pass

        listener = threading.Thread(target=listen)
        listener.start()

        sender = ob.OscSender("127.0.0.1", port)
        state = ob.HandState(True, 0.42, 0.58, 0.11, 0.77, "pinch", 3)
        ok = sender.send(state)
        listener.join(timeout=4)
        sock.close()

        self.assertTrue(ok, "send() reported failure")
        self.assertTrue(received, "no UDP packet arrived at the listener")

        bundle = OscBundle(received[0])
        addresses = [message.address for message in bundle]
        expected_addresses = [address for address, _ in ob.build_messages(state)]
        self.assertEqual(addresses, expected_addresses)


if __name__ == "__main__":
    unittest.main()
