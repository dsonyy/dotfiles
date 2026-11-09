import os
import subprocess
import time
from pathlib import Path

DISARMED = Path.home() / ".alarm"
W, H = 1280, 720
FRAME = W * H * 3
STEP = 8
PIXEL_DELTA = 25
CHANGED_SHARE = 0.03


def camera() -> subprocess.Popen:
    return subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-f", "v4l2", "-input_format", "mjpeg", "-video_size", f"{W}x{H}",
         "-i", "/dev/video0", "-vf", "fps=1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
    )


def read(cam: subprocess.Popen) -> bytes:
    frame = cam.stdout.read(FRAME)
    if len(frame) < FRAME:
        raise SystemExit("camera stream ended")
    return frame


def thumbnail(frame: bytes) -> list[int]:
    return [frame[(y * W + x) * 3 + 1] for y in range(0, H, STEP) for x in range(0, W, STEP)]


def send(frame: bytes) -> None:
    jpeg = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-video_size", f"{W}x{H}",
         "-i", "-", "-f", "mjpeg", "-"],
        input=frame, capture_output=True, check=True,
    ).stdout
    subprocess.run(
        ["curl", "-s", "-4", "--max-time", "30", "-F", f"chat_id={os.environ['TELEGRAM_CHAT_ID']}",
         "-F", "photo=@-;filename=cam.jpg",
         f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendPhoto"],
        input=jpeg, capture_output=True,
    )


def main() -> None:
    cam = previous = None
    while True:
        if DISARMED.exists():
            if cam:
                cam.kill()
                cam.wait()
                cam = previous = None
            time.sleep(1)
            continue
        if not cam:
            cam = camera()
            # the first frames are dark until auto exposure settles
            read(cam)
            read(cam)
        frame = read(cam)
        current = thumbnail(frame)
        if previous and sum(abs(a - b) > PIXEL_DELTA for a, b in zip(current, previous)) > CHANGED_SHARE * len(current):
            send(frame)
        previous = current


if __name__ == "__main__":
    main()
