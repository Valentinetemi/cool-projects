import pathlib
import sys
import unittest
from collections import namedtuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import gesture_math as gm  # noqa: E402

FakeLandmark = namedtuple("FakeLandmark", "x y z")


def make_hand(points):
    """Build a 21-point landmark list. `points` maps index -> (x, y, z);
    any index not given defaults to (0.5, 0.5, 0.0)."""
    return [
        FakeLandmark(*points.get(i, (0.5, 0.5, 0.0))) for i in range(21)
    ]


class PalmCenterTests(unittest.TestCase):
    def test_averages_palm_landmarks(self):
        landmarks = make_hand(
            {0: (0, 0, 0), 5: (1, 1, 0), 9: (0.5, 0.5, 0), 13: (0.4, 0.6, 0), 17: (0.6, 0.4, 0)}
        )
        x, y = gm.palm_center(landmarks)
        self.assertAlmostEqual(x, (0 + 1 + 0.5 + 0.4 + 0.6) / 5)
        self.assertAlmostEqual(y, (0 + 1 + 0.5 + 0.6 + 0.4) / 5)

    def test_clamps_to_unit_range(self):
        landmarks = make_hand({i: (1.8, -0.4, 0) for i in gm.PALM_LANDMARK_INDICES})
        x, y = gm.palm_center(landmarks)
        self.assertEqual((x, y), (1.0, 0.0))


class SmoothCoordinateTests(unittest.TestCase):
    def test_first_call_passes_through(self):
        self.assertEqual(gm.smooth_coordinate(None, (0.2, 0.3)), (0.2, 0.3))

    def test_applies_exponential_average(self):
        result = gm.smooth_coordinate((0.0, 0.0), (1.0, 1.0))
        self.assertAlmostEqual(result[0], gm.SMOOTHING_ALPHA)
        self.assertAlmostEqual(result[1], gm.SMOOTHING_ALPHA)


class LandmarkToPixelTests(unittest.TestCase):
    def test_clamps_within_frame_bounds(self):
        landmark = FakeLandmark(1.5, -0.5, 0.0)
        x, y = gm.landmark_to_pixel(landmark, frame_width=100, frame_height=50)
        self.assertEqual((x, y), (99, 0))

    def test_maps_center_point(self):
        landmark = FakeLandmark(0.5, 0.5, 0.0)
        x, y = gm.landmark_to_pixel(landmark, frame_width=200, frame_height=100)
        self.assertEqual((x, y), (100, 50))


class HandScaleTests(unittest.TestCase):
    def test_never_zero_even_when_degenerate(self):
        landmarks = make_hand({0: (0.5, 0.5, 0), 9: (0.5, 0.5, 0)})
        self.assertGreater(gm.hand_scale(landmarks), 0)

    def test_reflects_wrist_to_knuckle_distance(self):
        landmarks = make_hand({0: (0.5, 0.9, 0), 9: (0.5, 0.6, 0)})
        self.assertAlmostEqual(gm.hand_scale(landmarks), 0.3, places=6)


class PinchDistanceTests(unittest.TestCase):
    def test_small_when_tips_touch(self):
        landmarks = make_hand(
            {0: (0.5, 0.9, 0), 9: (0.5, 0.6, 0), 4: (0.5, 0.5, 0), 8: (0.51, 0.5, 0)}
        )
        self.assertLess(gm.pinch_distance(landmarks), gm.PINCH_DISTANCE_THRESHOLD)

    def test_large_when_tips_are_apart(self):
        landmarks = make_hand(
            {0: (0.5, 0.9, 0), 9: (0.5, 0.6, 0), 4: (0.1, 0.5, 0), 8: (0.9, 0.5, 0)}
        )
        self.assertGreater(gm.pinch_distance(landmarks), gm.PINCH_DISTANCE_THRESHOLD)


class HandOpennessTests(unittest.TestCase):
    def _hand_with_tip_distance(self, tip_distance_from_palm):
        # Wrist/knuckles fixed so hand_scale == 0.3; all 5 tips placed
        # `tip_distance_from_palm` away from the palm center on the x axis.
        palm_points = {i: (0.5, 0.6, 0) for i in (5, 9, 13, 17)}
        palm_points[0] = (0.5, 0.9, 0)
        tips = {
            i: (0.5 + tip_distance_from_palm, 0.6, 0) for i in gm.FINGER_TIP_INDICES
        }
        return make_hand({**palm_points, **tips})

    def test_low_for_curled_fingers(self):
        landmarks = self._hand_with_tip_distance(0.02)
        self.assertLess(gm.hand_openness(landmarks), gm.GRAB_OPENNESS_THRESHOLD)

    def test_high_for_spread_fingers(self):
        landmarks = self._hand_with_tip_distance(0.9)
        self.assertGreater(gm.hand_openness(landmarks), gm.OPEN_PALM_OPENNESS_THRESHOLD)

    def test_clamped_to_one(self):
        landmarks = self._hand_with_tip_distance(50.0)
        self.assertEqual(gm.hand_openness(landmarks), 1.0)


class ClassifyGestureTests(unittest.TestCase):
    def test_pinch_takes_priority_over_grab(self):
        gesture = gm.classify_gesture(pinch_dist=0.05, openness=0.05)
        self.assertEqual(gesture, gm.GESTURE_PINCH)

    def test_grab_when_closed_and_not_pinching(self):
        gesture = gm.classify_gesture(pinch_dist=0.9, openness=0.1)
        self.assertEqual(gesture, gm.GESTURE_GRAB)

    def test_open_palm_when_spread_wide(self):
        gesture = gm.classify_gesture(pinch_dist=0.9, openness=0.9)
        self.assertEqual(gesture, gm.GESTURE_OPEN_PALM)

    def test_neutral_in_between(self):
        gesture = gm.classify_gesture(pinch_dist=0.9, openness=0.5)
        self.assertEqual(gesture, gm.GESTURE_NEUTRAL)


class GestureIdTests(unittest.TestCase):
    def test_ids_are_stable(self):
        self.assertEqual(gm.gesture_id(gm.GESTURE_NONE), 0)
        self.assertEqual(gm.gesture_id(gm.GESTURE_NEUTRAL), 1)
        self.assertEqual(gm.gesture_id(gm.GESTURE_OPEN_PALM), 2)
        self.assertEqual(gm.gesture_id(gm.GESTURE_PINCH), 3)
        self.assertEqual(gm.gesture_id(gm.GESTURE_GRAB), 4)


if __name__ == "__main__":
    unittest.main()
