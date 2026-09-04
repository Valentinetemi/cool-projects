# TouchDesigner Integration Guide

This is the receiving half of Matter Bending: how to pull the OSC stream
from `hand_tracker.py` (see [OSC_SCHEMA.md](OSC_SCHEMA.md)) into
TouchDesigner and use it to drive a particle/water simulation.

**Fastest path**: run `touchdesigner/build_network.py` once inside
TouchDesigner and it builds everything described below for you, then saves
`touchdesigner/matterbending.toe`. See
[../touchdesigner/README.md](../touchdesigner/README.md) for the exact
steps and what to do with any warnings it prints. The rest of this guide
explains *what* that script builds and *why*, so you can extend or debug
it — it's also a complete manual walkthrough if you'd rather build the
network by hand.

TouchDesigner wasn't available in the environment this was developed in,
so none of this has been run inside real TouchDesigner — node/parameter
names below are TD's long-stable, well-documented conventions, but treat
first contact with the generated network as a verification pass, not a
sure thing.

## 1. Receive the OSC values

1. Add an **OSC In CHOP**, named `osc_hand`. Set:
   - `Network Port` = `9000` (must match `--osc-port`, default `9000`)
   - `Local Address` = blank (listens on all interfaces) or `127.0.0.1`
   - `Split Values` = On
2. Add a **Null CHOP** named `hand_data`, fed from `osc_hand` — everything
   downstream reads from here, not `osc_hand` directly, so you can swap
   the OSC source later (e.g. for a recorded take) without rewiring.
3. TouchDesigner names each incoming OSC address as one channel, replacing
   `/` with `:`. With `Split Values` on you should see 7 channels once
   `hand_tracker.py` is running: `present`, `palm:x`, `palm:y`,
   `pinch_distance`, `openness`, `gesture_id` (and a `gesture` channel that
   won't resolve numerically, since it's a string).
   - Exact channel naming can vary slightly by TouchDesigner version —
     open the OSC In CHOP's viewer while `hand_tracker.py --debug-interval 0.5`
     is running to confirm the live names, and update the `CHANNEL_*`
     constants in `matterbending_callbacks.py` if they differ.

Quick verification: with `hand_tracker.py` running and a hand in frame,
`hand_data`'s `present` channel should read `1`, and `palm:x`/`palm:y`
should move between 0 and 1 as you move your hand.

## 2. The particle/water system

`build_network.py` builds a classic SOP-based particle system inside a
Geometry COMP, `geo1`:

- `source1` (Sphere SOP) — where particles are born.
- `particle1` (Particle SOP) — the simulation itself.
- `attract1` / `turbulence1` (Force SOPs) — merged together (`merge1`) and
  fed into `particle1`'s force input. These are what gestures drive (below).
- `glow_mat1` (Constant MAT) — a flat, bright cyan-ish color; the "glow"
  comes from the render chain (step 5), not the material itself.
- `cam1` / `light1` — a basic camera pulled back on Z, and a light (mostly
  unused since Constant MAT ignores lighting, but harmless to have).
- `render1` — renders `geo1` through `cam1`.

## 3. palm_x/palm_y -> matter position

Rather than a chain of Fit/Math CHOPs (whose exact parameter names are
harder to guess reliably from outside TD), the mapping happens directly in
Python, in the Frame Start callback (`matterbending_callbacks.py`,
`update_matter()`):

```python
world_x = (palm_x - 0.5) * 2.0 * WORLD_HALF_WIDTH
world_y = (0.5 - palm_y) * 2.0 * WORLD_HALF_HEIGHT
attractor.par.tx = world_x
attractor.par.ty = world_y
```

`palm_y` is flipped (image convention has `y=0` at the top; TD's world
space is Y-up) so moving your hand up moves the matter up. `attract1`'s
position is what actually tracks the hand — it's the anchor every force
below pulls toward or pushes away from.

## 4. pinch = attract, grab = stronger deformation, open_palm = repel

All three read `gesture_id` from `hand_data` and set targets for
`attract1` and `turbulence1`, smoothed frame-to-frame so forces don't jump:

| Gesture | `attract1.strength` target | `turbulence1.strength` target |
|---|---|---|
| `pinch` | `+1.0` (pulls in) | `0` |
| `grab` | `+1.8` (pulls in *harder* than pinch) | `+0.6` (adds rough, chaotic distortion) |
| `open_palm` | `-openness * 1.5` (pushes out, more the wider the hand is spread) | `0` |
| `neutral` / no hand | `0` | `0` |

Grab isn't just "pinch but stronger" — the added turbulence force gives it
a visibly different, rougher character (deformation, not just attraction),
matching the idea that a full grab should disturb the matter more than a
light pinch. Tune `PINCH_ATTRACT_STRENGTH` / `GRAB_ATTRACT_STRENGTH` /
`GRAB_TURBULENCE_STRENGTH` / `OPEN_PALM_REPEL_SCALE` at the top of
`matterbending_callbacks.py` to taste.

## 5. presence = visibility/reset

Also in `update_matter()`:

- `geo1.display` and `geo1.render` follow `present` directly — the
  particle system disappears the instant no hand is detected, and
  reappears the instant one is.
- On the rising edge of `present` (hand was absent last frame, is present
  this frame), `particle1` gets a reset pulse — so each time your hand
  re-enters frame, the simulation restarts clean rather than resuming
  wherever it drifted to while you were gone.

## 6. Glowing, water-like look

The render chain after `render1`:

```
render1 --> blur1 (soft blur) --+
    |                            +--> glow_comp1 (Add) --> trail_comp1 (Add) --> final_out
    +----------------------------+                              ^
                                                                   |
                        feedback1 <-- level1 (dim ~10%/frame) <---+
```

- **Bloom**: `blur1` blurs the sharp render; `glow_comp1` adds the blur
  back on top of the original — bright areas glow instead of just
  overlapping opaquely.
- **Trails**: `feedback1` loops the composited output back a frame later,
  dimmed slightly each time by `level1`, and `trail_comp1` adds that fading
  history back in — this reads as fluid motion/streaks rather than
  discrete blips.
- **Color**: `glow_mat1`'s flat cyan-white color plus the additive
  glow/trail chain is what actually reads as "water" — no per-particle
  velocity-based coloring in this first version (a natural next tweak: feed
  particle speed into a Ramp TOP-driven color).

`build_network.py` also creates `glow_glsl1`, a single-pass GLSL bloom
using [`../touchdesigner/glow_bloom.frag`](../touchdesigner/glow_bloom.frag),
as an optional alternative to the blur+composite pair above — it's left
unwired since its uniform parameters need one manual "Setup Parameters"
click inside TD before they're scriptable (the build script's summary
flags this).

## 7. Later: transform particles into an avatar

Not part of this first version, but the network is built to support it:

1. Get a point cloud of your target avatar shape — a SOP built from a
   mesh (`Points SOP` sampling a model's surface) or a skeleton rig's joint
   positions.
2. Store those target positions in a texture (a **TOP** where each pixel
   encodes one target point's `xyz`) or a CHOP, matched 1:1 to your
   particle count.
3. Blend each particle's position target between "chaotic/attractor-driven"
   (current behavior) and "pulled toward its assigned avatar point" using
   a single `assemble` scalar (`0` = fully chaotic, `1` = fully assembled).
4. `assemble1` (a Constant CHOP) already exists as this placeholder,
   already ramped by `matterbending_callbacks.py`: sustained `pinch`/`grab`
   ramps it toward `1`, `open_palm` ramps it back toward `0`. Nothing
   consumes it yet — that's the next iteration's work (the target point
   cloud and the per-particle blend itself don't exist yet).

## Files

- `touchdesigner/build_network.py` — run once inside TD to build all of
  the above and save the `.toe`.
- `touchdesigner/matterbending_callbacks.py` — the frame-by-frame gesture
  logic (single source of truth; `build_network.py` loads it verbatim).
- `touchdesigner/glow_bloom.frag` — optional single-pass GLSL bloom.
- `touchdesigner/README.md` — exact manual steps and a network diagram.

## Troubleshooting

- **No channels in OSC In CHOP**: confirm `hand_tracker.py` is actually
  running and printing debug lines, and that `--osc-port` matches the
  CHOP's `Network Port`. If TouchDesigner is on a different machine than
  the camera, `--osc-host` must be that machine's IP, not `127.0.0.1`, and
  the OSC In CHOP's `Local Address` should be blank (not `127.0.0.1`) so it
  accepts external connections.
- **Values arrive but never change**: check the `present` channel first —
  if it's stuck at `0`, MediaPipe isn't detecting a hand (lighting,
  distance from camera, or the `--camera-index` pointing at the wrong
  device are the usual causes).
- **Channel names don't match the script**: open the OSC In CHOP's channel
  list live (see step 1) and update the `CHANNEL_*` constants at the top
  of `matterbending_callbacks.py` to match.
- **A parameter the build script tried to set doesn't exist on your TD
  version**: check the script's printed `MANUAL FIXUPS NEEDED` list — it
  names the exact node and value to set by hand.
