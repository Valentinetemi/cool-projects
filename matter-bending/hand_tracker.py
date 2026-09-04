from pathlib import Path
import time

import cv2
import mediapipe as mp


MODEL_PATH = Path(__file__).resolve().with_name("hand_landmarker.task")

# MediaPipe's 21 hand landmarks connected as a hand skeleton.
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)

# Wrist and the four finger-base knuckles form a stable palm position.
PALM_LANDMARK_INDICES = (0, 5, 9, 13, 17)
SMOOTHING_ALPHA = 0.25


def landmark_to_pixel(landmark, frame_width, frame_height):
    """Convert a normalized MediaPipe landmark to a safe pixel position."""
    x = max(0, min(frame_width - 1, int(landmark.x * frame_width)))
    y = max(0, min(frame_height - 1, int(landmark.y * frame_height)))
    return x, y


def draw_hand_landmarks(frame, landmarks):
    """Draw the Tasks API landmark list using OpenCV."""
    frame_height, frame_width = frame.shape[:2]
    pixel_landmarks = [
        landmark_to_pixel(landmark, frame_width, frame_height)
        for landmark in landmarks
    ]

    for start_index, end_index in HAND_CONNECTIONS:
        cv2.line(
            frame,
            pixel_landmarks[start_index],
            pixel_landmarks[end_index],
            (80, 220, 80),
            2,
        )

    for point in pixel_landmarks:
        cv2.circle(frame, point, 4, (255, 180, 60), -1)


def palm_center(landmarks):
    """Return one normalized control coordinate near the hand's center."""
    x = sum(landmarks[index].x for index in PALM_LANDMARK_INDICES) / len(
        PALM_LANDMARK_INDICES
    )
    y = sum(landmarks[index].y for index in PALM_LANDMARK_INDICES) / len(
        PALM_LANDMARK_INDICES
    )
    return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))


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


def main():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"Hand Landmarker model not found: {MODEL_PATH}\n"
            "Download the full float16 hand_landmarker.task model and place it "
            "beside hand_tracker.py."
        )

    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.7,
        min_hand_presence_confidence=0.7,
        min_tracking_confidence=0.7,
    )

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam 0")

    smoothed_control = None
    last_timestamp_ms = -1

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
                    draw_hand_landmarks(frame, landmarks)

                    smoothed_control = smooth_coordinate(
                        smoothed_control,
                        palm_center(landmarks),
                    )
                    control_x, control_y = smoothed_control

                    print(f"({control_x:.3f}, {control_y:.3f})")

                    frame_height, frame_width = frame.shape[:2]
                    control_pixel = (
                        min(frame_width - 1, int(control_x * frame_width)),
                        min(frame_height - 1, int(control_y * frame_height)),
                    )
                    cv2.circle(frame, control_pixel, 8, (0, 0, 255), -1)
                    cv2.putText(
                        frame,
                        f"control: ({control_x:.3f}, {control_y:.3f})",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 255),
                        2,
                    )
                else:
                    smoothed_control = None

                cv2.imshow("Matter Bending - Hand Tracking", frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
