"""Unit tests for hand_tracker.py's camera-handling helpers.

These only exercise the pure/duck-typed helpers (parse_args,
probe_camera_index, format_probe_result, run_camera_diagnostics,
warm_up_camera) against a fake cv2 stand-in -- hand_tracker.py defers its
real `import cv2` into functions specifically so this module can be
imported and tested without opencv-python installed (see
scripts/validate.sh).
"""

import io
import pathlib
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import hand_tracker as ht  # noqa: E402


class FakeFrame:
    """Minimal stand-in for a numpy frame -- only .shape is read."""

    def __init__(self, height, width):
        self.shape = (height, width, 3)


class FakeCapture:
    """Stand-in for cv2.VideoCapture with scripted open/read behavior.

    `frames` is a list of either (height, width) tuples (a successful read)
    or None (a failed read); once exhausted, reads keep failing.
    """

    def __init__(self, opened, frames):
        self._opened = opened
        self._frames = list(frames)
        self.released = False

    def isOpened(self):
        return self._opened

    def read(self):
        if not self._frames:
            return False, None
        frame_spec = self._frames.pop(0)
        if frame_spec is None:
            return False, None
        height, width = frame_spec
        return True, FakeFrame(height, width)

    def release(self):
        self.released = True


class FakeCv2:
    """Stand-in for the cv2 module: maps camera index -> (opened, frames)."""

    def __init__(self, captures_by_index):
        self._captures_by_index = captures_by_index
        self.captures = []

    def VideoCapture(self, index):
        opened, frames = self._captures_by_index.get(index, (False, []))
        capture = FakeCapture(opened, list(frames))
        self.captures.append(capture)
        return capture


class ParseArgsTests(unittest.TestCase):
    def test_defaults(self):
        args = ht.parse_args([])
        self.assertEqual(args.camera_index, 0)
        self.assertFalse(args.headless)
        self.assertFalse(args.diagnose_camera)

    def test_camera_index_flag(self):
        args = ht.parse_args(["--camera-index", "2"])
        self.assertEqual(args.camera_index, 2)

    def test_headless_flag(self):
        args = ht.parse_args(["--headless"])
        self.assertTrue(args.headless)

    def test_diagnose_camera_flag(self):
        args = ht.parse_args(["--diagnose-camera"])
        self.assertTrue(args.diagnose_camera)


class ProbeCameraIndexTests(unittest.TestCase):
    def test_index_not_opened(self):
        cv2 = FakeCv2({})
        result = ht.probe_camera_index(0, cv2, warmup_attempts=1, warmup_delay=0)
        self.assertEqual(
            result,
            {"index": 0, "opened": False, "read_ok": False, "width": None, "height": None},
        )

    def test_opened_but_never_reads(self):
        cv2 = FakeCv2({0: (True, [None, None])})
        result = ht.probe_camera_index(0, cv2, warmup_attempts=2, warmup_delay=0)
        self.assertTrue(result["opened"])
        self.assertFalse(result["read_ok"])

    def test_opened_and_reads_after_warmup(self):
        # First read fails (simulating macOS warm-up delay), second succeeds.
        cv2 = FakeCv2({0: (True, [None, (480, 640)])})
        result = ht.probe_camera_index(0, cv2, warmup_attempts=5, warmup_delay=0)
        self.assertTrue(result["opened"])
        self.assertTrue(result["read_ok"])
        self.assertEqual(result["width"], 640)
        self.assertEqual(result["height"], 480)

    def test_releases_capture(self):
        cv2 = FakeCv2({0: (True, [(480, 640)])})
        ht.probe_camera_index(0, cv2, warmup_attempts=1, warmup_delay=0)
        self.assertTrue(cv2.captures[0].released)


class FormatProbeResultTests(unittest.TestCase):
    def test_not_opened(self):
        line = ht.format_probe_result(
            {"index": 1, "opened": False, "read_ok": False, "width": None, "height": None}
        )
        self.assertIn("index 1", line)
        self.assertIn("could not open", line)

    def test_opened_no_frame(self):
        line = ht.format_probe_result(
            {"index": 1, "opened": True, "read_ok": False, "width": None, "height": None}
        )
        self.assertIn("never returned a frame", line)

    def test_ok(self):
        line = ht.format_probe_result(
            {"index": 1, "opened": True, "read_ok": True, "width": 640, "height": 480}
        )
        self.assertIn("OK", line)
        self.assertIn("640x480", line)


class RunCameraDiagnosticsTests(unittest.TestCase):
    def test_reports_working_index(self):
        cv2 = FakeCv2(
            {
                0: (False, []),
                1: (True, [(480, 640)]),
                2: (True, [None]),
            }
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            results = ht.run_camera_diagnostics(
                [0, 1, 2], cv2, warmup_attempts=2, warmup_delay=0
            )
        output = buffer.getvalue()
        self.assertEqual([r["index"] for r in results], [0, 1, 2])
        self.assertIn("Working index(es): [1]", output)
        self.assertIn("--camera-index 1", output)

    def test_reports_no_working_index(self):
        cv2 = FakeCv2({0: (False, []), 1: (False, []), 2: (False, [])})
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            ht.run_camera_diagnostics([0, 1, 2], cv2, warmup_attempts=1, warmup_delay=0)
        output = buffer.getvalue()
        self.assertIn("No camera index produced a frame", output)


class WarmUpCameraTests(unittest.TestCase):
    def test_succeeds_immediately(self):
        cap = FakeCapture(True, [(480, 640)])
        self.assertTrue(ht.warm_up_camera(cap, attempts=3, delay=0))

    def test_succeeds_after_retries(self):
        cap = FakeCapture(True, [None, None, (480, 640)])
        self.assertTrue(ht.warm_up_camera(cap, attempts=5, delay=0))

    def test_gives_up_after_exhausting_attempts(self):
        cap = FakeCapture(True, [None, None])
        self.assertFalse(ht.warm_up_camera(cap, attempts=2, delay=0))


if __name__ == "__main__":
    unittest.main()
