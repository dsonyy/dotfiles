import fcntl
import os
import subprocess
import time
from pathlib import Path

DISARMED = Path.home() / ".alarm"
CAMERA_LOCK = Path("/tmp/camera.lock")
PIXEL_DELTA = 25
CHANGED_SHARE = 0.03


def ffmpeg(args: list[str], data: bytes | None = None) -> bytes:
    return subprocess.run(["ffmpeg", "-loglevel", "error", *args], input=data, capture_output=True, check=True).stdout


def photo() -> bytes:
    # the camera is exclusive, meeting-bot takes the same lock for its photo button
    with CAMERA_LOCK.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        # without nobuffer ffmpeg spends ~10x more CPU buffering the camera stream than capturing the frame
        return ffmpeg(["-fflags", "nobuffer", "-f", "v4l2", "-input_format", "mjpeg",
                       "-video_size", "1280x720", "-i", "/dev/video0", "-frames:v", "1", "-c:v", "copy", "-f", "mjpeg", "-"])


def thumbnail(jpeg: bytes) -> bytes:
    return ffmpeg(["-f", "mjpeg", "-i", "-", "-vf", "scale=160:90", "-f", "rawvideo", "-pix_fmt", "gray", "-"], jpeg)


def send(jpeg: bytes) -> None:
    subprocess.run(
        ["curl", "-s", "-4", "--max-time", "30", "-F", f"chat_id={os.environ['TELEGRAM_CHAT_ID']}",
         "-F", "photo=@-;filename=cam.jpg",
         f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendPhoto"],
        input=jpeg, capture_output=True,
    )


def main() -> None:
    previous = None
    while True:
        started = time.monotonic()
        if DISARMED.exists():
            previous = None
        else:
            jpeg = photo()
            current = thumbnail(jpeg)
            if previous and sum(abs(a - b) > PIXEL_DELTA for a, b in zip(current, previous)) > CHANGED_SHARE * len(current):
                send(jpeg)
            previous = current
        time.sleep(max(0, 1 - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
