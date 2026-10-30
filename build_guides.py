"""Create mobile guide videos without changing analysis reference originals.

Requires ffmpeg on PATH. Run from any directory: python3 build_guides.py
Only the five explicit reference videos are published, never user uploads.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
VIDEOS = {
    "squat-side": "squat_side_raw.mp4",
    "squat-front": "squat_front_raw.mp4",
    "lunge-side": "lunge_side_raw.mp4",
    "lunge-front": "lunge_front_raw.mp4",
    "lateral_raise-front": "sidelateralraise_front_raw.mov",
}


def main():
    output = ROOT / "data/guides"
    output.mkdir(parents=True, exist_ok=True)
    for name, source in VIDEOS.items():
        target = output / f"{name}.mp4"
        temporary = output / f".{name}.tmp.mp4"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(ROOT / "data/raw" / source),
            "-map", "0:v:0", "-an", "-map_metadata", "-1",
            "-vf", "scale=720:720:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",
            "-r", "30", "-c:v", "libx264", "-preset", "fast",
            "-crf", "25", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(temporary),
        ], check=True)
        temporary.replace(target)
        print(f"{target.name}: {target.stat().st_size:,} bytes", flush=True)


if __name__ == "__main__":
    main()
