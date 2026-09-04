# TouchDesigner Integration Guide

This is the receiving half of Matter Bending: how to pull the OSC stream
from `hand_tracker.py` (see [OSC_SCHEMA.md](OSC_SCHEMA.md)) into
TouchDesigner and use it to drive a particle simulation.

TouchDesigner isn't available in this development environment, so no
`.toe` project file ships with this repo — a binary `.toe` built blind,
without ever opening it in TouchDesigner, would be more likely to be
subtly broken than helpful. Instead, this guide gives you the exact node
network to build (every node, parameter, and connection) plus a ready-to-paste
Python callback script (`touchdesigner/matterbending_callbacks.py`) and an
optional GLSL glow pass (`touchdesigner/glow_bloom.frag`). Node names below
match the callback script — use them as given, or update the script if you
rename anything.

## 1. Receive the OSC values

1. Add an **OSC In CHOP**. Set:
   - `Network Port` = `9000` (must match `--osc-port`, default `9000`)
   - `Local Address` = blank (listens on all interfaces) or `127.0.0.1`
   - `Address Filter` = blank (accept everything under `/matterbending/hand`)
   - `Split Values` = On
   - Rename this CHOP to `osc_hand`.
2. TouchDesigner names each incoming OSC address as one channel, replacing
   `/` with `:`. With `Split Values` on, you should see 7 channels once
   `hand_tracker.py` is running, e.g. `present`, `palm:x`, `palm:y`,
   `pinch_distance`, `openness`, `gesture_id` (and a `gesture` channel that
   won't resolve numerically, since it's a string — ignore it in CHOPs and
   read it from a **DAT** instead if you need the text label).
   - Exact channel naming can vary slightly by TouchDesigner version —
     open the OSC In CHOP's viewer while `hand_tracker.py --debug-interval 0.5`
     is running to confirm the live channel names on your install, and
     adjust `matterbending_callbacks.py`'s channel lookups if they differ.
3. Add a **Lag CHOP** or **Filter CHOP** after `osc_hand` (optional) if you
   want extra smoothing on top of the Python-side exponential smoothing —
   useful mainly if your camera framerate is low and jittery.
4. Add a **Null CHOP** named `hand_data` after that — reference this one
   from everything downstream, not `osc_hand` directly, so you can swap the
   OSC source later (e.g. for a recorded take) without rewiring.

Quick verification: with `hand_tracker.py` running and a hand in frame,
`hand_data`'s `present` channel should read `1`, and `palm:x`/`palm:y`
should move between 0 and 1 as you move your hand.

## 2. Map palm position to particle movement

1. Add a **Fit CHOP** referencing `hand_data`, selecting only `palm:x` and
   `palm:y`. Remap from the incoming `0–1` range to whatever world-space
   bounds your particle system spawns/lives in — e.g. `-1` to `1` for a
   typical centered TouchDesigner scene. Name it `palm_world`.
2. Add a **CHOP to** conversion appropriate to your particle system:
   - **Particles GPU TOP / POPs**: feed `palm_world` into a **Force POP**
     or the `Position` parameter of an **Attract POP**, via CHOP-to-DAT-export
     or by referencing the channel directly in the POP's parameter
     (right-click the parameter → *Export CHOP* → `palm_world`).
   - **SOP-based particles (Particle SOP / Force SOP)**: export
     `palm_world` to a **Null SOP**'s transform, or directly to a
     **Force SOP**'s `Position` parameter, and use that as your attractor
     source location.
3. This gives you a live 2D (or 3D, if you add a constant Z) point that
   tracks the user's palm — the anchor for every effect below.

## 3. Pinch = grab / attract

1. Add an **Attract POP** (or **Force SOP** in Attract mode) named
   `attract1`, positioned at `palm_world`.
2. Its strength should be **0 when not pinching, positive when pinching**.
   Two ways to drive that:
   - **CHOP math**: `Select CHOP` → `gesture_id` channel → `Math CHOP`
     (`Convert` range so `gesture_id == 3` maps to `1`, everything else to
     `0`) → export to `attract1`'s `Strength` parameter, then multiply by
     your desired max attract force.
   - **Python** (simpler to read, see `matterbending_callbacks.py`): an
     **Execute DAT** (`Frame Start`) reads `hand_data['gesture_id']` each
     frame and sets `op('attract1').par.strength` directly — `1.0` if the
     gesture id is `3` (pinch), else `0.0`. This is what the provided
     script does.
3. Tune `attract1`'s falloff/radius so the pull feels local to the hand
   rather than affecting the whole simulation at once.

## 4. Open palm = release / repel

1. Reuse `attract1` (or add a second POP, `repel1`, at the same position)
   and drive its strength **negative**, scaled by `openness`, when
   `gesture_id == 2` (open palm):
   - `strength = -openness * REPEL_SCALE` when open palm, else unaffected.
2. `matterbending_callbacks.py`'s `update_attractor()` implements exactly
   this: pinch pulls in, open palm pushes out proportional to how wide the
   hand is spread, grab and neutral leave strength at (or decaying toward)
   zero.

## 5. Glowing, water-like particle look

A convincing "digital water" look in TouchDesigner is mostly about color,
motion blur/trails, and additive glow — not the particle sim itself:

1. **Sprite**: give your Particle GPU TOP / POP a soft circular sprite
   (a radial-gradient TOP, white center fading to transparent, works well)
   instead of hard points.
2. **Color**: drive particle color from velocity or age using a **Ramp
   TOP** — blue/cyan core fading to white at the core and deep blue/violet
   at the edges reads as "water"; feed speed into the ramp's lookup via a
   CHOP-to-TOP or the POP's built-in color-by-speed option if available.
3. **Additive compositing**: render particles to their own TOP, then
   **Composite TOP** set to `Add` when combining with the background —
   this is what makes overlapping particles glow instead of just
   overlapping opaquely.
4. **Bloom**: duplicate the particle render, run it through a **Blur TOP**
   (moderate radius), then **Composite (Add)** the blurred copy back on
   top of the sharp one. This is a cheap, reliable bloom without needing a
   dedicated glow operator. `glow_bloom.frag` (optional) does the same
   thing as a single GLSL TOP pass if you'd rather not chain Blur+Composite.
5. **Trails**: a **Feedback TOP** looping the composited output back into
   itself each frame, attenuated slightly (multiply by ~`0.85–0.93` via a
   **Level TOP** each loop), gives particles trailing streaks instead of
   discrete blips — this reads as fluid motion rather than sparks.

## 6. Later: transform particles into an avatar

This is a natural next iteration, not part of the first TouchDesigner-ready
version, but the network above is built to support it:

1. Get a point cloud of your target avatar shape — a SOP built from a
   mesh (`Points SOP` sampling a model's surface) or a skeleton rig's joint
   positions.
2. Store those target positions in a texture (a **TOP** where each pixel
   encodes one target point's `xyz`) or a CHOP, matched 1:1 to your
   particle count.
3. In your particle update shader (or a POP's custom force), blend each
   particle's velocity/position target between "chaotic/attractor-driven"
   (current behavior) and "pulled toward its assigned avatar point",
   using a single `assemble` scalar (`0` = fully chaotic, `1` = fully
   assembled) driven by gesture — e.g. sustained `pinch` or `grab` over
   time ramps `assemble` toward `1` (particles converge into the avatar
   shape), `open_palm` ramps it back toward `0` (avatar scatters apart).
4. `matterbending_callbacks.py` includes a stubbed `assemble` value (see
   `STATE['assemble']`) already being tracked from gesture history, ready
   to export to a shader uniform or CHOP channel once you build the target
   point cloud.

## Files in this guide

- `touchdesigner/matterbending_callbacks.py` — paste into an **Execute
  DAT** (or a **Text DAT** referenced by one) set to run on `Frame Start`.
  Reads `hand_data`, drives `attract1`, and tracks the `assemble` value for
  the avatar step above. Every `op(...)` path is called out as a constant
  at the top of the file — update those to match your node names.
- `touchdesigner/glow_bloom.frag` — optional single-pass GLSL bloom, for a
  **GLSL TOP**, as an alternative to the Blur+Composite chain in step 5.

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
  list live (see step 1.2) and update the `CHANNEL_*` constants at the top
  of `matterbending_callbacks.py` to match.
