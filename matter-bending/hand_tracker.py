"""MediaPipe hand-tracking layer for Matter Bending.

Reads the webcam, runs MediaPipe's Hand Landmarker, derives a smoothed
palm-center position plus pinch/openness/gesture state, and streams that
state to TouchDesigner over OSC every frame. See docs/OSC_SCHEMA.md for the
wire format and docs/TOUCHDESIGNER_GUIDE.md for the receiving end.

The geometry/gesture math lives in gesture_math.py and the OSC wire format
in osc_bridge.py -- both are dependency-free and unit tested on their own;
this file is the thin orchestration layer that wires camera capture,
MediaPipe inference, on-screen debug drawing, and OSC output together.
"""

import argparse
import sys
import time
from pathlib import Path

import gesture_math as gm
import osc_bridge as ob

MODEL_PATH = Path(__file__).resolve().with_name("hand_landmarker.task")

DEFAULT_OSC_HOST = "127.0.0.1"
DEFAULT_OSC_PORT = 9000
DEFAULT_DEBUG_INTERVAL = 0.2  # seconds between printed debug lines


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--osc-host",
        default=DEFAULT_OSC_HOST,
        help=f"TouchDesigner OSC receiver host (default: {DEFAULT_OSC_HOST})",
    )
    parser.add_argument(
        "--osc-port",
        type=int,
        default=DEFAULT_OSC_PORT,
        help=f"TouchDesigner OSC receiver port (default: {DEFAULT_OSC_PORT})",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="OpenCV camera index to open (default: 0)",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=MODEL_PATH,
        help=f"Path to hand_landmarker.task (default: {MODEL_PATH})",
    )
    parser.add_argument(
        "--debug-interval",
        type=float,
        default=DEFAULT_DEBUG_INTERVAL,
        help="Minimum seconds between printed debug lines; 0 prints every "
        f"frame (default: {DEFAULT_DEBUG_INTERVAL})",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Skip the OpenCV preview window (camera + OSC only, lower overhead)",
    )
    return parser.parse_args(argv)


def require_model(model_path):
    """Exit with a clear, friendly message if the model file is missing.

    Called before touching the camera or MediaPipe so a missing model fails
    immediately rather than after the webcam light turns on.
    """
    if model_path.is_file():
        return

    print(
        f"Hand Landmarker model not found: {model_path}\n\n"
        "Fetch it with:\n"
        "    bash scripts/download_model.sh\n\n"
        "or download the float16 hand_landmarker.task model manually from "
        "the MediaPipe model zoo (see README.md) and place it beside "
        "hand_tracker.py.",
        file=sys.stderr,
    )
    sys.exit(1)


def draw_hand_landmarks(frame, landmarks):
    """Draw the Tasks API landmark list using OpenCV."""
    import cv2

    frame_height, frame_width = frame.shape[:2]
    pixel_landmarks = [
        gm.landmark_to_pixel(landmark, frame_width, frame_height)
        for landmark in landmarks
    ]

    for start_index, end_index in gm.HAND_CONNECTIONS:
        cv2.line(
            frame,
            pixel_landmarks[start_index],
            pixel_landmarks[end_index],
            (80, 220, 80),
            2,
        )

    for point in pixel_landmarks:
        cv2.circle(frame, point, 4, (255, 180, 60), -1)


def build_hand_state(landmarks, smoothed_control):
    """Compute the full OSC-ready HandState for one frame's landmarks."""
    control_x, control_y = smoothed_control
    pinch = gm.pinch_distance(landmarks)
    openness = gm.hand_openness(landmarks)
    gesture = gm.classify_gesture(pinch, openness)
    return ob.HandState(
        present=True,
        palm_x=control_x,
        palm_y=control_y,
        pinch_distance=pinch,
        openness=openness,
        gesture=gesture,
        gesture_id=gm.gesture_id(gesture),
    )


def main(argv=None):
    args = parse_args(argv)
    require_model(args.model_path)

    # Imported after require_model() so a missing model fails fast without
    # paying for the (fairly slow) mediapipe/cv2 import first.
    import cv2
    import mediapipe as mp

    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(args.model_path)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.7,
        min_hand_presence_confidence=0.7,
        min_tracking_confidence=0.7,
    )

    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        print(
            f"Could not open webcam {args.camera_index}. Check that no other "
            "application is using the camera and that this process has "
            "camera permission.",
            file=sys.stderr,
        )
        sys.exit(1)

    sender = ob.OscSender(args.osc_host, args.osc_port)
    print(f"Sending OSC to {args.osc_host}:{args.osc_port} (Ctrl+C to quit)")

    smoothed_control = None
    last_timestamp_ms = -1
    last_debug_print = 0.0

    try:
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker:
            while True:
                success, frame = cap.read()

                if not success:
                    break

                # Mirror the camera so movement feels natural.
                frame = cv2.flip(frame, 1)

                # OpenCV uses BGR, while a MediaPipe SRGB Image expects RGB data.
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb_frame,
                )

                # VIDEO mode requires a monotonically increasing frame timestamp.
                timestamp_ms = time.monotonic_ns() // 1_000_000
                timestamp_ms = max(timestamp_ms, last_timestamp_ms + 1)
                last_timestamp_ms = timestamp_ms

                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if result.hand_landmarks:
                    landmarks = result.hand_landmarks[0]

                    smoothed_control = gm.smooth_coordinate(
                        smoothed_control,
                        gm.palm_center(landmarks),
                    )
                    state = build_hand_state(landmarks, smoothed_control)

                    if not args.headless:
                        draw_hand_landmarks(frame, landmarks)
                        frame_height, frame_width = frame.shape[:2]
                        control_pixel = (
                            min(frame_width - 1, int(state.palm_x * frame_width)),
                            min(frame_height - 1, int(state.palm_y * frame_height)),
                        )
                        cv2.circle(frame, control_pixel, 8, (0, 0, 255), -1)
                        cv2.putText(
                            frame,
                            state.gesture,
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.8,
                            (255, 255, 255),
                            2,
                        )
                else:
                    smoothed_control = None
                    state = ob.absent_state()

                # UDP send is fire-and-forget and non-blocking, so this never
                # stalls the camera loop even if TouchDesigner isn't running.
                sender.send(state)

                now = time.monotonic()
                if now - last_debug_print >= args.debug_interval:
                    print(ob.format_debug_line(state))
                    last_debug_print = now

                if not args.headless:
                    cv2.imshow("Matter Bending - Hand Tracking", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        cap.release()
        if not args.headless:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
