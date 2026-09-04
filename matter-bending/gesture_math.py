"""Pure geometry and gesture-classification helpers for hand landmarks.

Nothing here imports cv2, mediapipe, or an OSC library. Every function takes
plain landmark-like objects that expose `.x`, `.y`, `.z` (normalized 0-1
coordinates) -- MediaPipe's own landmark type already satisfies this, and so
does a simple namedtuple, which is what the test suite uses. Keeping this
module dependency-free means the gesture logic can be unit tested on any
machine, even one without MediaPipe/OpenCV installed.
"""

import math

# MediaPipe Hand Landmarker's 21 landmark indices we care about.
WRIST = 0
THUMB_TIP = 4
INDEX_TIP = 8
MIDDLE_TIP = 12
RING_TIP = 16
PINKY_TIP = 20
MIDDLE_FINGER_MCP = 9

FINGER_TIP_INDICES = (THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP)

# Wrist and the four finger-base knuckles form a stable palm position.
PALM_LANDMARK_INDICES = (0, 5, 9, 13, 17)

# The full 21-point hand skeleton, as (start, end) landmark index pairs.
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)

SMOOTHING_ALPHA = 0.25

# Gesture thresholds. These are reasonable defaults, not calibrated against
# a specific camera/hand -- if gestures don't trigger reliably for you,
# watch the --debug console output and nudge these constants to match your
# observed pinch/openness values.
PINCH_DISTANCE_THRESHOLD = 0.35
GRAB_OPENNESS_THRESHOLD = 0.35
OPEN_PALM_OPENNESS_THRESHOLD = 0.75
OPENNESS_NORMALIZATION = 2.2

GESTURE_NONE = "none"
GESTURE_NEUTRAL = "neutral"
GESTURE_OPEN_PALM = "open_palm"
GESTURE_PINCH = "pinch"
GESTURE_GRAB = "grab"

GESTURE_IDS = {
    GESTURE_NONE: 0,
    GESTURE_NEUTRAL: 1,
    GESTURE_OPEN_PALM: 2,
    GESTURE_PINCH: 3,
    GESTURE_GRAB: 4,
}


def _xyz(landmark):
    return (landmark.x, landmark.y, landmark.z)


def _distance(point_a, point_b):
    return math.sqrt(
        (point_a[0] - point_b[0]) ** 2
        + (point_a[1] - point_b[1]) ** 2
        + (point_a[2] - point_b[2]) ** 2
    )


def landmark_to_pixel(landmark, frame_width, frame_height):
    """Convert a normalized MediaPipe landmark to a safe pixel position."""
    x = max(0, min(frame_width - 1, int(landmark.x * frame_width)))
    y = max(0, min(frame_height - 1, int(landmark.y * frame_height)))
    return x, y


def palm_center(landmarks):
    """Return one normalized (x, y) control coordinate near the hand's center."""
    x = sum(landmarks[index].x for index in PALM_LANDMARK_INDICES) / len(
        PALM_LANDMARK_INDICES
    )
    y = sum(landmarks[index].y for index in PALM_LANDMARK_INDICES) / len(
        PALM_LANDMARK_INDICES
    )
    return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))


def _palm_center_3d(landmarks):
    n = len(PALM_LANDMARK_INDICES)
    x = sum(landmarks[i].x for i in PALM_LANDMARK_INDICES) / n
    y = sum(landmarks[i].y for i in PALM_LANDMARK_INDICES) / n
    z = sum(landmarks[i].z for i in PALM_LANDMARK_INDICES) / n
    return (x, y, z)


def smooth_coordinate(previous, current):
    """Reduce frame-to-frame landmark jitter with an exponential average."""
    if previous is None:
        return current

    previous_x, previous_y = previous
    current_x, current_y = current
    return (
        previous_x + SMOOTHING_ALPHA * (current_x - previous_x),
        previous_y + SMOOTHING_ALPHA * (current_y - previous_y),
    )


def hand_scale(landmarks):
    """Wrist-to-middle-knuckle distance.

    This stays roughly constant regardless of finger pose, so it is used as
    a per-hand reference length that makes pinch distance and openness
    (mostly) invariant to how far the hand is from the camera.
    """
    scale = _distance(_xyz(landmarks[WRIST]), _xyz(landmarks[MIDDLE_FINGER_MCP]))
    return max(scale, 1e-6)


def pinch_distance(landmarks):
    """Thumb-tip-to-index-tip distance, normalized by hand scale.

    Small values mean the thumb and index finger are touching (a pinch).
    """
    scale = hand_scale(landmarks)
    return _distance(_xyz(landmarks[THUMB_TIP]), _xyz(landmarks[INDEX_TIP])) / scale


def hand_openness(landmarks):
    """0 (closed fist) .. 1 (fully open hand), clamped.

    Based on the average distance of all five fingertips from the palm
    center, normalized by hand scale.
    """
    scale = hand_scale(landmarks)
    palm = _palm_center_3d(landmarks)
    average_tip_distance = sum(
        _distance(_xyz(landmarks[i]), palm) for i in FINGER_TIP_INDICES
    ) / len(FINGER_TIP_INDICES)
    normalized = (average_tip_distance / scale) / OPENNESS_NORMALIZATION
    return max(0.0, min(1.0, normalized))


def classify_gesture(pinch_dist, openness):
    """Classify a discrete gesture from pinch distance and openness.

    Pinch takes priority over grab/open since a pinch pose can otherwise
    also read as a partially-closed hand.
    """
    if pinch_dist < PINCH_DISTANCE_THRESHOLD:
        return GESTURE_PINCH
    if openness < GRAB_OPENNESS_THRESHOLD:
        return GESTURE_GRAB
    if openness > OPEN_PALM_OPENNESS_THRESHOLD:
        return GESTURE_OPEN_PALM
    return GESTURE_NEUTRAL


def gesture_id(gesture_name):
    """Numeric id for a gesture name, for OSC/CHOP-friendly consumption."""
    return GESTURE_IDS[gesture_name]
