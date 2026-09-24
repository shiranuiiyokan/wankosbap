import json
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageOps
from renderer import render_cta

FPS = 30
SCENE_TAIL = float(os.getenv("SCENE_TAIL", "0.55"))
READING_MAP_PATH = Path(__file__).parent / "voice_reading_map.json"


def run(cmd):
    print("+", " ".join(str(x) for x in cmd), flush=True)
    timeout = max(30, int(os.getenv("FFMPEG_TIMEOUT_SECONDS", "300")))
    try:
        subprocess.run(cmd, check=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout}s") from exc


def _load_reading_map():
    if not READING_MAP_PATH.is_file():
        return {}
    try:
        data = json.loads(READING_MAP_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


READING_MAP = _load_reading_map()


def _speech_text(scene: dict) -> str:
    text = str(scene.get("narration_reading") or scene.get("narration") or "").strip()
    for source in sorted(READING_MAP, key=len, reverse=True):
        text = text.replace(source, str(READING_MAP[source]))
    return text


def audio_duration(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path),
    ], text=True)
    return float(json.loads(out)["format"]["duration"])


def _dimensions(job: dict):
    video = job.get("video", {})
    series = str(job.get("series", "")).lower()
    if video.get("width") and video.get("height"):
        return int(video["width"]), int(video["height"])
    if series in {"long", "long_form", "longform"}:
        return 1920, 1080
    return 1080, 1920


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _cjk_fontfile() -> str:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    try:
        matched = subprocess.check_output(
            ["fc-match", "-f", "%{file}", "Noto Sans CJK JP:style=Bold"],
            text=True,
        ).strip()
        if matched and Path(matched).is_file():
            return matched
    except Exception:
        pass
    raise RuntimeError("Japanese CJK font not found; install fonts-noto-cjk")


def _video_filter(width: int, height: int, overlay_textfile: Path | None = None) -> str:
    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:white",
        "setsar=1",
        f"fps={FPS}",
    ]
    if overlay_textfile is not None:
        fontfile = _escape_filter_path(Path(_cjk_fontfile()))
        textfile = _escape_filter_path(overlay_textfile)
        fontsize = max(44, int(min(width, height) * 0.066))
        top_margin = int(height * 0.08)
        border = max(14, int(fontsize * 0.30))
        line_spacing = max(8, int(fontsize * 0.12))
        filters.append(
            "drawtext="
            f"fontfile='{fontfile}':"
            f"textfile='{textfile}':"
            "fontcolor=white:"
            f"fontsize={fontsize}:"
            f"line_spacing={line_spacing}:"
            "box=1:boxcolor=black@0.56:"
            f"boxborderw={border}:"
            "x=(w-text_w)/2:"
            f"y={top_margin}"
        )
    return ",".join(filters)


def render_scene(image: Path, audio: Path, output: Path, width: int, height: int,
                 fixed_duration=None, overlay_textfile: Path | None = None):
    duration = float(fixed_duration) if fixed_duration is not None else audio_duration(audio) + SCENE_TAIL
    run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(image), "-i", str(audio),
        "-vf", _video_filter(width, height, overlay_textfile),
        "-af", f"apad,atrim=0:{duration:.3f}",
        "-t", f"{duration:.3f}", "-r", str(FPS),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-movflags", "+faststart", str(output),
    ])
    return output


def render_silent_scene(image: Path, duration: float, output: Path,
                        width: int, height: int, overlay_textfile: Path | None = None):
    duration = max(0.5, float(duration))
    run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(image),
        "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=48000",
        "-t", f"{duration:.3f}", "-vf", _video_filter(width, height, overlay_textfile),
        "-r", str(FPS), "-c:v", "libx264", "-preset", "medium",
        "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-b:a", "192k", "-ar", "48000", "-shortest",
        "-movflags", "+faststart", str(output),
    ])
    return output


def concatenate(files, output: Path):
    manifest = output.with_suffix(".concat.txt")
    manifest.write_text("\n".join(f"file '{p.resolve()}'" for p in files), encoding="utf-8")
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest),
        "-c", "copy", "-movflags", "+faststart", str(output),
    ])
    return output




def _sanitize_image(path: Path, output_dir: Path, index: int) -> Path:
    """Decode with Pillow and re-save a clean RGB JPEG before FFmpeg.

    This strips malformed/oversized PNG metadata/chunks that can make FFmpeg's
    image parser loop indefinitely on otherwise viewable generated images.
    """
    target = output_dir / f"sanitized_{index:02d}.jpg"
    with Image.open(path) as source:
        source.load()
        clean = ImageOps.exif_transpose(source).convert("RGB")
        clean.save(target, "JPEG", quality=95, subsampling=0)
    return target


def render_scheduled_job(job: dict, job_dir: Path, output_dir: Path, synthesize_fn):
    output_dir.mkdir(parents=True, exist_ok=True)
    width, height = _dimensions(job)
    narration_enabled = bool(job.get("narration_enabled", True))
    rendered = []

    for i, scene in enumerate(job["scenes"], start=1):
        image = _sanitize_image(job_dir / scene["image"], output_dir, i)
        clip = output_dir / f"scene_{i:02d}.mp4"
        narration = scene.get("narration")
        speech_text = _speech_text(scene)
        overlay_textfile = None
        overlay_text = str(scene.get("overlay_text") or "").strip()
        if overlay_text:
            overlay_textfile = output_dir / f"overlay_{i:02d}.txt"
            overlay_textfile.write_text(overlay_text, encoding="utf-8")
        if narration_enabled and narration:
            audio = output_dir / f"voice_{i:02d}.wav"
            synthesize_fn(speech_text, audio)
            render_scene(
                image,
                audio,
                clip,
                width,
                height,
                scene.get("duration") if job.get("fixed_scene_durations") else None,
                overlay_textfile,
            )
        else:
            render_silent_scene(
                image,
                scene.get("duration", 3.0),
                clip,
                width,
                height,
                overlay_textfile,
            )
        rendered.append(clip)

    append_cta = job.get("append_common_cta")
    if append_cta is None:
        append_cta = height > width
    if append_cta and height > width:
        rendered.append(render_cta(output_dir))

    return concatenate(rendered, output_dir / "final.mp4")
