# Matter Bending OSC Schema

`hand_tracker.py` sends one frame of hand state to TouchDesigner as a
single OSC bundle (all seven messages in one UDP packet, so TouchDesigner
never sees a partially-updated frame).

- **Default target**: `127.0.0.1:9000` (UDP) — override with `--osc-host` /
  `--osc-port`
- **Send rate**: once per processed camera frame (camera-framerate
  dependent, typically ~15-30 Hz)
- **Source of truth**: `osc_bridge.py`'s `build_messages()`. If this doc and
  the code ever disagree, the code wins — but they're kept in sync by
  `tests/test_osc_bridge.py::BuildMessagesTests`.

## Addresses

| Address | Type | Range | Description |
|---|---|---|---|
| `/matterbending/hand/present` | int32 | `0` or `1` | `1` if a hand is currently detected in frame, else `0`. All other fields hold their "absent" defaults below when this is `0`. |
| `/matterbending/hand/palm/x` | float32 | `0.0`–`1.0` | Smoothed palm-center X, normalized to frame width. `0.0` = left edge, `1.0` = right edge. Mirrored (camera is flipped), so movement matches what the user sees on screen. |
| `/matterbending/hand/palm/y` | float32 | `0.0`–`1.0` | Smoothed palm-center Y, normalized to frame height. `0.0` = top edge, `1.0` = bottom edge. |
| `/matterbending/hand/pinch_distance` | float32 | `0.0`–~`2.0`+ | Distance between thumb tip and index fingertip, normalized by the hand's own wrist-to-knuckle length (so it's roughly invariant to how far the hand is from the camera). Smaller = closer together. A pinch is classified below `0.35`. |
| `/matterbending/hand/openness` | float32 | `0.0`–`1.0` (clamped) | How spread out the hand is: average distance of all five fingertips from the palm center, normalized the same way as pinch distance and clamped to `[0, 1]`. `0` = closed fist, `1` = fully spread. |
| `/matterbending/hand/gesture` | string | one of `none`, `neutral`, `open_palm`, `pinch`, `grab` | Discrete classification, see below. |
| `/matterbending/hand/gesture_id` | int32 | `0`–`4` | Numeric id for the same gesture, for TouchDesigner CHOPs (which don't carry strings). |

## Gesture values

| `gesture` | `gesture_id` | Meaning | Trigger |
|---|---|---|---|
| `none` | `0` | No hand in frame | `present == 0` |
| `neutral` | `1` | Hand present, no specific pose | Doesn't match any rule below |
| `open_palm` | `2` | Hand spread wide | `openness > 0.75` |
| `pinch` | `3` | Thumb and index touching | `pinch_distance < 0.35` (checked first — takes priority over grab) |
| `grab` | `4` | Fingers curled, not pinching | `openness < 0.35` |

Thresholds live in `gesture_math.py` (`PINCH_DISTANCE_THRESHOLD`,
`GRAB_OPENNESS_THRESHOLD`, `OPEN_PALM_OPENNESS_THRESHOLD`) and aren't
calibrated to any specific camera or hand — watch the `--debug` console
output and adjust them if gestures don't trigger reliably for your setup.

## "Absent" defaults

When no hand is detected, every frame still sends all seven addresses (so
downstream CHOPs never hold stale values), with:

```
present        = 0
palm/x         = 0.0
palm/y         = 0.0
pinch_distance = 0.0
openness       = 0.0
gesture        = "none"
gesture_id     = 0
```

## Example frame (pinching, center of frame)

```
/matterbending/hand/present        1
/matterbending/hand/palm/x         0.502
/matterbending/hand/palm/y         0.488
/matterbending/hand/pinch_distance 0.121
/matterbending/hand/openness       0.340
/matterbending/hand/gesture        "pinch"
/matterbending/hand/gesture_id     3
```

This matches the line `hand_tracker.py --debug-interval` prints to the
console, e.g.:

```
present=1  palm=(0.502, 0.488)  pinch=0.121  openness=0.340  gesture=pinch(3)
```
