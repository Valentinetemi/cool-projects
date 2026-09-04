import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import gesture_math as gm  # noqa: E402
import osc_bridge as ob  # noqa: E402

EXPECTED_ADDRESSES = [
    "/matterbending/hand/present",
    "/matterbending/hand/palm/x",
    "/matterbending/hand/palm/y",
    "/matterbending/hand/pinch_distance",
    "/matterbending/hand/openness",
    "/matterbending/hand/gesture",
    "/matterbending/hand/gesture_id",
]


class AbsentStateTests(unittest.TestCase):
    def test_defaults(self):
        state = ob.absent_state()
        self.assertFalse(state.present)
        self.assertEqual(state.gesture, gm.GESTURE_NONE)
        self.assertEqual(state.gesture_id, 0)


class BuildMessagesTests(unittest.TestCase):
    def setUp(self):
        self.state = ob.HandState(
            present=True,
            palm_x=0.25,
            palm_y=0.75,
            pinch_distance=0.12,
            openness=0.88,
            gesture=gm.GESTURE_OPEN_PALM,
            gesture_id=gm.gesture_id(gm.GESTURE_OPEN_PALM),
        )

    def test_addresses_match_schema_in_order(self):
        addresses = [address for address, _ in ob.build_messages(self.state)]
        self.assertEqual(addresses, EXPECTED_ADDRESSES)

    def test_values_round_trip(self):
        values = dict(ob.build_messages(self.state))
        self.assertEqual(values["/matterbending/hand/present"], 1)
        self.assertAlmostEqual(values["/matterbending/hand/palm/x"], 0.25)
        self.assertAlmostEqual(values["/matterbending/hand/palm/y"], 0.75)
        self.assertAlmostEqual(values["/matterbending/hand/pinch_distance"], 0.12)
        self.assertAlmostEqual(values["/matterbending/hand/openness"], 0.88)
        self.assertEqual(values["/matterbending/hand/gesture"], "open_palm")
        self.assertEqual(values["/matterbending/hand/gesture_id"], 2)

    def test_value_types_are_osc_safe(self):
        for address, value in ob.build_messages(self.state):
            self.assertIsInstance(value, (int, float, str), msg=address)

    def test_absent_state_produces_present_zero(self):
        values = dict(ob.build_messages(ob.absent_state()))
        self.assertEqual(values["/matterbending/hand/present"], 0)
        self.assertEqual(values["/matterbending/hand/gesture"], "none")


class FormatDebugLineTests(unittest.TestCase):
    def test_contains_key_fields(self):
        state = ob.HandState(True, 0.123, 0.456, 0.05, 0.9, gm.GESTURE_PINCH, 3)
        line = ob.format_debug_line(state)
        self.assertIn("0.123", line)
        self.assertIn("0.456", line)
        self.assertIn("pinch", line)


class OscSenderLazyImportTests(unittest.TestCase):
    def test_module_import_does_not_require_python_osc(self):
        # This test file already imported osc_bridge above without
        # python-osc installed (see requirements.txt) -- OscSender only
        # imports pythonosc inside its own methods, so simply having the
        # class available confirms the module-level import stayed clean.
        self.assertTrue(hasattr(ob, "OscSender"))


if __name__ == "__main__":
    unittest.main()
