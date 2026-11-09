import os
import subprocess
import time
from pathlib import Path

DISARMED = Path.home() / ".alarm"
PIXEL_DELTA = 25
CHANGED_SHARE = 0.03


def camera() -> subprocess.Popen:
    return subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-f", "v4l2", "-input_format", "mjpeg", "-video_size", "1280x720",
         "-i", "/dev/video0", "-c:v", "copy", "-f", "mjpeg", "-"],
        stdout=subprocess.PIPE,
    )


def thumbnail(jpeg: bytes) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "mjpeg", "-i", "-", "-vf", "scale=160:90",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        input=jpeg, capture_output=True, check=True,
    ).stdout


def send(jpeg: bytes) -> None:
    subprocess.run(
        ["curl", "-s", "-4", "--max-time", "30", "-F", f"chat_id={os.environ['TELEGRAM_CHAT_ID']}",
         "-F", "photo=@-;filename=cam.jpg",
         f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendPhoto"],
        input=jpeg, capture_output=True,
    )


def main() -> None:
    cam = previous = None
    buffer = b""
    checked = 0.0
    while True:
        if DISARMED.exists():
            if cam:
                cam.kill()
                cam.wait()
                cam = previous = None
                buffer = b""
            time.sleep(1)
            continue
        if not cam:
            cam = camera()
        chunk = cam.stdout.read1(1 << 16)
        if not chunk:
            raise SystemExit("camera stream ended")
        buffer += chunk
        # the camera streams 30 JPEGs per second; only the newest complete one is decoded, once per second
        end = buffer.rfind(b"\xff\xd9")
        start = buffer.rfind(b"\xff\xd8", 0, end)
        if end < 0 or start < 0:
            continue
        jpeg = buffer[start:end + 2]
        buffer = buffer[end + 2:]
        if time.monotonic() - checked < 1:
            continue
        checked = time.monotonic()
        current = thumbnail(jpeg)
        if previous and sum(abs(a - b) > PIXEL_DELTA for a, b in zip(current, previous)) > CHANGED_SHARE * len(current):
            send(jpeg)
        previous = current


if __name__ == "__main__":
    main()
