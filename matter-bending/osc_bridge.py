"""Builds and sends the Matter Bending OSC message set to TouchDesigner.

Message *building* is separated from message *sending* so the wire format
can be unit tested without a real socket or python-osc installed -- only
`OscSender` touches the network, and it imports `pythonosc` lazily so that
importing this module never requires it. See docs/OSC_SCHEMA.md for the
full address reference.
"""

from dataclasses import dataclass

import gesture_math

ADDRESS_PREFIX = "/matterbending/hand"


@dataclass(frozen=True)
class HandState:
    present: bool
    palm_x: float
    palm_y: float
    pinch_distance: float
    openness: float
    gesture: str
    gesture_id: int


def absent_state():
    """The state sent when no hand is currently detected in frame."""
    return HandState(
        present=False,
        palm_x=0.0,
        palm_y=0.0,
        pinch_distance=0.0,
        openness=0.0,
        gesture=gesture_math.GESTURE_NONE,
        gesture_id=gesture_math.gesture_id(gesture_math.GESTURE_NONE),
    )


def build_messages(state):
    """Return an ordered list of (osc_address, value) pairs for one frame."""
    prefix = ADDRESS_PREFIX
    return [
        (f"{prefix}/present", int(state.present)),
        (f"{prefix}/palm/x", float(state.palm_x)),
        (f"{prefix}/palm/y", float(state.palm_y)),
        (f"{prefix}/pinch_distance", float(state.pinch_distance)),
        (f"{prefix}/openness", float(state.openness)),
        (f"{prefix}/gesture", str(state.gesture)),
        (f"{prefix}/gesture_id", int(state.gesture_id)),
    ]


def format_debug_line(state):
    """Human-readable one-line summary of a HandState, for console output."""
    return (
        f"present={int(state.present)}  "
        f"palm=({state.palm_x:.3f}, {state.palm_y:.3f})  "
        f"pinch={state.pinch_distance:.3f}  "
        f"openness={state.openness:.3f}  "
        f"gesture={state.gesture}({state.gesture_id})"
    )


class OscSender:
    """Sends one HandState per frame to TouchDesigner as a single OSC bundle.

    All messages for a frame go out in one UDP packet (an OSC bundle) so
    TouchDesigner never reads a partial frame of values. UDP send is
    fire-and-forget and non-blocking, so this never stalls the camera loop;
    if TouchDesigner isn't listening, `send()` just returns False instead of
    raising.
    """

    def __init__(self, host, port):
        from pythonosc.udp_client import SimpleUDPClient

        self._client = SimpleUDPClient(host, port)

    def send(self, state):
        from pythonosc import osc_bundle_builder, osc_message_builder

        try:
            bundle = osc_bundle_builder.OscBundleBuilder(
                osc_bundle_builder.IMMEDIATELY
            )
            for address, value in build_messages(state):
                builder = osc_message_builder.OscMessageBuilder(address=address)
                builder.add_arg(value)
                bundle.add_content(builder.build())
            self._client.send(bundle.build())
            return True
        except OSError:
            return False
