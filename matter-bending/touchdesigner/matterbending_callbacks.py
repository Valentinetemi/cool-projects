"""Matter Bending TouchDesigner frame callback.

Runs every frame from an Execute DAT (Frame Start). Reads the OSC hand
channels from hand_data, then:

  palm_x/palm_y -> attract1's position ("matter position")
  pinch         -> attract1 pulls in at PINCH_ATTRACT_STRENGTH
  grab          -> attract1 pulls in harder (GRAB_ATTRACT_STRENGTH) AND
                    turbulence1 kicks in -- a visibly different, rougher
                    "deformation" than a plain pinch, not just a stronger
                    version of the same force
  open_palm     -> attract1 pushes out (repel), scaled by openness
  presence      -> geo1's visibility follows `present`; a hand reappearing
                    (0 -> 1) fires a reset pulse on particle1 so it starts
                    fresh rather than resuming wherever it drifted while
                    the hand was gone

Also writes a slowly-ramping `assemble` value (0..1) to assemble1, a
placeholder channel for the future avatar-assembly step described in
docs/TOUCHDESIGNER_GUIDE.md -- nothing consumes it yet.

build_network.py (in this same directory) loads this file's text verbatim
into a Text DAT (hand_logic1), and a small Execute DAT delegates to
hand_logic1.module.onFrameStart() each Frame Start -- so this file is the
single source of truth for the frame logic; it does not need editing after
the network is built, only if you change node names or want to retune the
constants below.

This file only runs meaningfully inside TouchDesigner (it uses TD's
built-in `op()`); outside TD, importing it will fail on the first `op()`
call, same as any other TD script.
"""

# --- Constants: adjust if you rename nodes or retune the response -----------

HAND_DATA_CHOP = "hand_data"
ATTRACTOR_OP = "attract1"
TURBULENCE_OP = "turbulence1"
GEO_OP = "geo1"
PARTICLE_SOP = "particle1"
ASSEMBLE_CHOP = "assemble1"

# Channel names as they appear in the OSC In CHOP with Split Values on.
# TouchDesigner turns "/matterbending/hand/palm/x" into "palm:x", etc.
# Verify these live against your OSC In CHOP's viewer if nothing responds --
# see docs/TOUCHDESIGNER_GUIDE.md's Troubleshooting section.
CHANNEL_PRESENT = "present"
CHANNEL_PALM_X = "palm:x"
CHANNEL_PALM_Y = "palm:y"
CHANNEL_OPENNESS = "openness"
CHANNEL_GESTURE_ID = "gesture_id"

GESTURE_NONE = 0
GESTURE_NEUTRAL = 1
GESTURE_OPEN_PALM = 2
GESTURE_PINCH = 3
GESTURE_GRAB = 4

# World-space bounds attract1 moves within; matches build_network.py's
# particle source extent. Widen/narrow to taste.
WORLD_HALF_WIDTH = 3.0
WORLD_HALF_HEIGHT = 3.0

PINCH_ATTRACT_STRENGTH = 1.0
GRAB_ATTRACT_STRENGTH = 1.8
GRAB_TURBULENCE_STRENGTH = 0.6
OPEN_PALM_REPEL_SCALE = 1.5

# How quickly attract/turbulence strength slides toward its target each
# frame (0-1; higher = snappier, lower = smoother/laggier).
FORCE_SMOOTHING = 0.15

# How fast `assemble` ramps toward 0/1 per frame. See guide step 6.
ASSEMBLE_RATE = 0.02

# Module-level state persists across frames as long as this DAT isn't
# re-cooked from scratch; TouchDesigner keeps Python module state alive
# between Execute DAT callback calls within a session.
STATE = {
    "assemble": 0.0,
    "was_present": False,
    "attract_strength": 0.0,
    "turbulence_strength": 0.0,
    # Resolved (candidate-name -> actual working par name) caches, so the
    # multi-candidate lookups below only pay their cost once.
    "resolved_pars": {},
}


def _read_channel(chop, name, default=0.0):
    if chop is None or name not in chop.chans():
        return default
    return float(chop[name][0])


def _set_par_any(op_ref, cache_key, candidates, value):
    """Set the first parameter name in `candidates` that exists on op_ref,
    remembering which one worked so later frames skip straight to it."""
    if op_ref is None:
        return False

    resolved = STATE["resolved_pars"].get(cache_key)
    if resolved:
        try:
            setattr(op_ref.par, resolved, value)
            return True
        except Exception:
            STATE["resolved_pars"].pop(cache_key, None)

    for name in candidates:
        try:
            setattr(op_ref.par, name, value)
            STATE["resolved_pars"][cache_key] = name
            return True
        except Exception:
            continue
    return False


def _pulse_par_any(op_ref, cache_key, candidates):
    if op_ref is None:
        return False

    resolved = STATE["resolved_pars"].get(cache_key)
    names = [resolved] + list(candidates) if resolved else list(candidates)
    for name in names:
        try:
            getattr(op_ref.par, name).pulse()
            STATE["resolved_pars"][cache_key] = name
            return True
        except Exception:
            continue
    return False


def update_matter():
    hand = op(HAND_DATA_CHOP)
    attractor = op(ATTRACTOR_OP)
    turbulence = op(TURBULENCE_OP)
    geo = op(GEO_OP)
    particle = op(PARTICLE_SOP)
    assemble_chop = op(ASSEMBLE_CHOP)

    if hand is None:
        return

    present = bool(_read_channel(hand, CHANNEL_PRESENT))
    palm_x = _read_channel(hand, CHANNEL_PALM_X, 0.5)
    palm_y = _read_channel(hand, CHANNEL_PALM_Y, 0.5)
    openness = _read_channel(hand, CHANNEL_OPENNESS)
    gesture_id = int(_read_channel(hand, CHANNEL_GESTURE_ID))

    # --- palm_x/palm_y -> matter position ---
    # palm is normalized 0-1 with y=0 at the top of frame (image convention);
    # TD's world space is Y-up, so flip Y on the way in.
    world_x = (palm_x - 0.5) * 2.0 * WORLD_HALF_WIDTH
    world_y = (0.5 - palm_y) * 2.0 * WORLD_HALF_HEIGHT

    if attractor is not None:
        _set_par_any(attractor, "attract_pos_x", ("tx", "px"), world_x)
        _set_par_any(attractor, "attract_pos_y", ("ty", "py"), world_y)

    # --- gesture -> force targets ---
    if not present:
        target_attract = 0.0
        target_turbulence = 0.0
    elif gesture_id == GESTURE_PINCH:
        target_attract = PINCH_ATTRACT_STRENGTH
        target_turbulence = 0.0
    elif gesture_id == GESTURE_GRAB:
        target_attract = GRAB_ATTRACT_STRENGTH
        target_turbulence = GRAB_TURBULENCE_STRENGTH
    elif gesture_id == GESTURE_OPEN_PALM:
        target_attract = -openness * OPEN_PALM_REPEL_SCALE
        target_turbulence = 0.0
    else:  # neutral
        target_attract = 0.0
        target_turbulence = 0.0

    STATE["attract_strength"] += (target_attract - STATE["attract_strength"]) * FORCE_SMOOTHING
    STATE["turbulence_strength"] += (
        target_turbulence - STATE["turbulence_strength"]
    ) * FORCE_SMOOTHING

    if attractor is not None:
        _set_par_any(attractor, "attract_strength", ("strength",), STATE["attract_strength"])
    if turbulence is not None:
        _set_par_any(
            turbulence, "turbulence_strength", ("strength",), STATE["turbulence_strength"]
        )

    # --- presence -> visibility/reset ---
    if geo is not None:
        geo.display = present
        geo.render = present

    if present and not STATE["was_present"] and particle is not None:
        _pulse_par_any(particle, "particle_reset", ("resetpulse", "reset"))
    STATE["was_present"] = present

    # --- avatar-assembly placeholder ramp ---
    if present and gesture_id in (GESTURE_PINCH, GESTURE_GRAB):
        STATE["assemble"] = min(1.0, STATE["assemble"] + ASSEMBLE_RATE)
    elif present and gesture_id == GESTURE_OPEN_PALM:
        STATE["assemble"] = max(0.0, STATE["assemble"] - ASSEMBLE_RATE)

    if assemble_chop is not None:
        _set_par_any(assemble_chop, "assemble_value", ("value0",), STATE["assemble"])


def onFrameStart(frame):
    update_matter()
    return
