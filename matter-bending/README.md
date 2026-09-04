# Matter Bending

Hand movements bend digital matter. A webcam tracks your hand with
MediaPipe; palm position, pinch, and openness stream out over OSC to
TouchDesigner, where they drive a particle/fluid simulation — the
long-term goal being a system where you can bend water, particles, or an
avatar with your bare hands.

## How it fits together

```
webcam --> hand_tracker.py (MediaPipe) --> OSC --> TouchDesigner (particles/fluid)
                                        \
                                         `--> (fallback) main.cpp / spatial, a
                                              standalone GLFW/OpenGL particle
                                              prototype with no hand input
```

- **`hand_tracker.py`** is the hand-tracking layer: 21-landmark detection,
  smoothed palm-center tracking, pinch distance, hand openness, and
  gesture classification (`open_palm` / `pinch` / `grab` / `neutral`),
  streamed to TouchDesigner at `127.0.0.1:9000` by default. See
  [docs/OSC_SCHEMA.md](docs/OSC_SCHEMA.md) for the exact wire format.
- **`gesture_math.py`** holds the pure geometry/gesture-classification
  functions, dependency-free and unit tested on their own.
- **`osc_bridge.py`** builds and sends the OSC messages, also unit tested
  independently of the network layer.
- **`main.cpp` / `spatial`** is the original standalone C++ particle
  simulation — kept as a fallback physics prototype with no hand input.
  It still builds and runs on its own; see [Fallback: the C++ simulation](#fallback-the-c-simulation).
- **`docs/TOUCHDESIGNER_GUIDE.md`** is the receiving half: exact node
  network, Python callback script, and an optional GLSL bloom pass.
- **`touchdesigner/`** holds the TouchDesigner side itself: a script that
  builds the full starter network (`build_network.py`), the frame-by-frame
  gesture logic it wires in (`matterbending_callbacks.py`), an optional
  GLSL bloom pass (`glow_bloom.frag`), and once generated, the project
  file itself (`matterbending.toe`). See
  [touchdesigner/README.md](touchdesigner/README.md) for exact steps.

## Setup

Requires Python 3.9+ and a webcam.

```bash
cd matter-bending
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # or requirements-dev.txt to also get pytest
bash scripts/download_model.sh   # fetches hand_landmarker.task
```

If `scripts/download_model.sh` can't reach the download URL, get the
float16 Hand Landmarker model manually from the
[MediaPipe model zoo](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)
and save it as `hand_landmarker.task` beside `hand_tracker.py`.

## Running the hand tracker

```bash
python3 hand_tracker.py
```

This opens the default webcam, shows a debug preview window with the hand
skeleton and current gesture overlaid, and streams OSC to
`127.0.0.1:9000`. Console output looks like:

```
Sending OSC to 127.0.0.1:9000 (Ctrl+C to quit)
present=1  palm=(0.502, 0.488)  pinch=0.121  openness=0.340  gesture=pinch(3)
```

Press `q` in the preview window (or Ctrl+C in the terminal) to stop.

Useful flags:

| Flag | Default | Purpose |
|---|---|---|
| `--osc-host` | `127.0.0.1` | Where TouchDesigner is listening |
| `--osc-port` | `9000` | OSC port |
| `--camera-index` | `0` | Which webcam to open |
| `--model-path` | `hand_landmarker.task` beside this file | Model location |
| `--debug-interval` | `0.2` | Seconds between printed debug lines (`0` = every frame) |
| `--headless` | off | Skip the OpenCV preview window (lower overhead, camera + OSC only) |

Run `python3 hand_tracker.py --help` for the full list. If the model file
is missing, it prints instructions and exits immediately — it won't open
the camera first.

## Connecting TouchDesigner

Fastest path: open TouchDesigner, open the Textport, and run
`touchdesigner/build_network.py` once — it builds the full starter network
(OSC input, particle/water system, gesture-driven forces, glow + trails)
and saves `touchdesigner/matterbending.toe`. Exact steps and what the
network looks like: [touchdesigner/README.md](touchdesigner/README.md).

To build it by hand instead, or to understand what the generated network
does: [docs/TOUCHDESIGNER_GUIDE.md](docs/TOUCHDESIGNER_GUIDE.md) covers
the full node network (palm → particle position, pinch → attract, grab →
stronger/rougher deformation, open palm → repel, presence → visibility and
reset, the glow/trail look).

Either way, first confirm the link itself works: add an **OSC In CHOP**,
set `Network Port` to `9000` (matching `--osc-port`) and `Split Values`
on, then run `python3 hand_tracker.py` — with a hand in frame, the CHOP's
`present` channel should read `1` and `palm:x`/`palm:y` should move as
your hand does.

## Testing

```bash
bash scripts/validate.sh
```

Compiles every module, runs the unit test suite (`gesture_math.py` and
`osc_bridge.py`'s message-building logic — pure functions, no camera or
network needed), and smoke-tests `hand_tracker.py`'s `--help` and
missing-model exit path. Or directly:

```bash
python3 -m unittest discover -s tests -v
```

What's *not* covered by automated tests, since they need hardware this
project can't assume: live camera capture, real MediaPipe inference
against actual hand video, and the TouchDesigner side of the OSC link —
verify those by running `hand_tracker.py` and watching the debug output
and TouchDesigner's OSC In CHOP together.

## Fallback: the C++ simulation

`main.cpp` is a standalone GLFW/OpenGL particle simulation (gravity +
floor bounce, no hand input) — a physics prototype kept as a fallback if
the TouchDesigner/OSC pipeline isn't available. The compiled binary
(`spatial`) isn't committed to git (see `.gitignore`); rebuild it with:

```bash
clang++ main.cpp -std=c++17 \
  -I$(brew --prefix glfw)/include -L$(brew --prefix glfw)/lib \
  -lglfw -framework OpenGL -framework Cocoa -framework IOKit -framework CoreVideo \
  -o spatial
./spatial
```

(Requires GLFW: `brew install glfw` on macOS.)

## Project layout

```
matter-bending/
├── hand_tracker.py              # camera capture, MediaPipe inference, OSC send (orchestration)
├── gesture_math.py               # pure palm/pinch/openness/gesture math (dependency-free)
├── osc_bridge.py                  # OSC message building + sending
├── main.cpp / spatial             # fallback C++ particle simulation (no hand input)
├── requirements.txt / requirements-dev.txt
├── scripts/
│   ├── download_model.sh          # fetches hand_landmarker.task
│   └── validate.sh                # compile + test + smoke-test
├── tests/
│   ├── test_gesture_math.py
│   ├── test_osc_bridge.py
│   └── test_osc_integration.py
├── docs/
│   ├── OSC_SCHEMA.md               # every OSC address, type, and range
│   └── TOUCHDESIGNER_GUIDE.md      # receiving-end node network + walkthrough
└── touchdesigner/
    ├── build_network.py            # run once inside TD: builds the whole network + saves the .toe
    ├── matterbending_callbacks.py  # frame-by-frame gesture logic (single source of truth)
    ├── glow_bloom.frag             # optional GLSL bloom pass
    ├── README.md                   # exact manual steps + network diagram
    └── matterbending.toe           # generated project (not present until you run build_network.py)
```

## What's next

Hand tracking → OSC → a scripted TouchDesigner particle/water network are
in place; `touchdesigner/build_network.py` builds the `.toe` for you (see
[touchdesigner/README.md](touchdesigner/README.md)). Not yet done:

- **Opening the generated project in real TouchDesigner** and fixing
  whatever the build script's `MANUAL FIXUPS NEEDED` list flags — it was
  written and syntax-checked without TouchDesigner installed, so this
  first run is a verification pass, not a formality.
- The avatar-formation step described in the TouchDesigner guide's
  "Later: transform particles into an avatar" section — `assemble1`
  already ramps with sustained pinch/grab and open palm, but nothing
  consumes it yet; the avatar point-cloud target and the per-particle
  blend still need building.
- Per-user calibration of the gesture thresholds in `gesture_math.py` and
  the force strengths in `matterbending_callbacks.py` — current defaults
  are reasonable guesses, not tuned against real camera data or a real TD
  render.
