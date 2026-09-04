"""Matter Bending TouchDesigner callbacks.

Paste this into an Execute DAT set to run on Frame Start (or into a Text
DAT that an Execute DAT calls). It reads the OSC hand-tracking channels and
drives a particle attractor: pinch pulls particles in, open palm pushes
them out (scaled by how wide the hand is spread), and grab/neutral relax
the attractor back toward zero.

See docs/TOUCHDESIGNER_GUIDE.md for the full node network this assumes.
Everything you're likely to need to change for your own network is in the
CONSTANTS block below -- node paths and channel names.
"""

# --- Constants: adjust these to match your network -------------------------

# Null CHOP downstream of the OSC In CHOP (see guide step 1).
HAND_DATA_CHOP = "hand_data"

# The attractor POP/SOP driven by pinch/open-palm (see guide steps 3-4).
ATTRACTOR_OP = "attract1"

# Channel names as they appear in the OSC In CHOP with Split Values on.
# TouchDesigner turns "/matterbending/hand/palm/x" into "palm:x", etc.
# Verify these live against your OSC In CHOP's viewer -- see the guide's
# Troubleshooting section if yours differ.
CHANNEL_PRESENT = "present"
CHANNEL_PALM_X = "palm:x"
CHANNEL_PALM_Y = "palm:y"
CHANNEL_PINCH_DISTANCE = "pinch_distance"
CHANNEL_OPENNESS = "openness"
CHANNEL_GESTURE_ID = "gesture_id"

# Gesture ids, matching docs/OSC_SCHEMA.md.
GESTURE_NONE = 0
GESTURE_NEUTRAL = 1
GESTURE_OPEN_PALM = 2
GESTURE_PINCH = 3
GESTURE_GRAB = 4

PINCH_ATTRACT_STRENGTH = 1.0
OPEN_PALM_REPEL_SCALE = 1.5

# How fast the avatar "assembled-ness" ramps toward its target each frame.
# Sustained pinch/grab ramps ASSEMBLE up toward 1; open palm ramps it back
# down toward 0. See guide step 6 -- unused until you wire up an avatar
# point-cloud target, but tracked here so it's ready.
ASSEMBLE_RATE = 0.02

# Module-level state persists across frames as long as this DAT isn't
# re-cooked from scratch; TouchDesigner keeps Python module state alive
# between Execute DAT callback calls within a session.
STATE = {"assemble": 0.0}


def _read_channel(chop, name, default=0.0):
    channel = chop[name] if name in chop.chans() else None
    if channel is None:
        return default
    return float(channel[0])


def update_attractor():
    hand = op(HAND_DATA_CHOP)
    attractor = op(ATTRACTOR_OP)
    if hand is None or attractor is None:
        return

    present = _read_channel(hand, CHANNEL_PRESENT)
    openness = _read_channel(hand, CHANNEL_OPENNESS)
    gesture_id = int(_read_channel(hand, CHANNEL_GESTURE_ID))

    if not present:
        strength = 0.0
    elif gesture_id == GESTURE_PINCH:
        strength = PINCH_ATTRACT_STRENGTH
    elif gesture_id == GESTURE_OPEN_PALM:
        strength = -openness * OPEN_PALM_REPEL_SCALE
    else:
        strength = 0.0

    attractor.par.strength = strength

    # Avatar-assembly ramp: pinch/grab nudge toward assembled, open palm
    # nudges toward scattered, neutral holds steady. See guide step 6.
    if present and gesture_id in (GESTURE_PINCH, GESTURE_GRAB):
        STATE["assemble"] = min(1.0, STATE["assemble"] + ASSEMBLE_RATE)
    elif present and gesture_id == GESTURE_OPEN_PALM:
        STATE["assemble"] = max(0.0, STATE["assemble"] - ASSEMBLE_RATE)


def onFrameStart(frame):
    update_attractor()
    return
