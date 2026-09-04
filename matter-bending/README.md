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

1. Start TouchDesigner, add an **OSC In CHOP**, set `Network Port` to
   `9000` (matching `--osc-port`), and `Split Values` on.
2. Run `python3 hand_tracker.py` — with a hand in frame, the CHOP's
   `present` channel should read `1` and `palm:x`/`palm:y` should move as
   your hand does.
3. Follow [docs/TOUCHDESIGNER_GUIDE.md](docs/TOUCHDESIGNER_GUIDE.md) for
   the full node network (palm → particle movement, pinch → attract, open
   palm → repel, the glow/trail look) and paste in
   `docs/touchdesigner/matterbending_callbacks.py` as your Execute DAT
   callback.

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
│   └── test_osc_bridge.py
└── docs/
    ├── OSC_SCHEMA.md               # every OSC address, type, and range
    ├── TOUCHDESIGNER_GUIDE.md      # receiving-end node network + walkthrough
    └── touchdesigner/
        ├── matterbending_callbacks.py  # paste into an Execute DAT
        └── glow_bloom.frag              # optional GLSL bloom pass
```

## What's next

The first TouchDesigner-ready version covers hand tracking → OSC →
(documented) particle attract/repel. Not yet built:

- An actual `.toe` project file, once this can be assembled and verified
  inside TouchDesigner itself rather than documented blind.
- The avatar-formation step described in the TouchDesigner guide's
  "Later: transform particles into an avatar" section — the OSC schema
  and callback script already track an `assemble` value for this, but the
  avatar point-cloud target and the shader blend between chaotic and
  assembled states aren't built yet.
- Per-user calibration of the gesture thresholds in `gesture_math.py` —
  current defaults are reasonable guesses, not tuned against real camera
  data.
