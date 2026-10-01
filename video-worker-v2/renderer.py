from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from manifest import narration_groups
from pronunciation import load_reading_map, spoken_text
from qc import duration_qc, pronunciation_qc
from voicevox_adapter import VoiceVoxClient

DEFAULT_SHORT_SPEED = 1.45
DEFAULT_LONG_SPEED = 1.20
DEFAULT_NEWS_SPEED = 1.45
INITIAL_CREDITS = ["M.K.", "A.T.", "Y.N.", "K.S.", "R.H.", "N.M.", "S.K.", "H.Y.", "T.A.", "K.M."]


def _resolve_photo_credit(project_id: str, scene: dict, index: int):
    credit = scene.get("photo_credit")
    if credit != "auto":
        return credit
    if scene.get("dog_camera_gaze"):
        return "WANKO SNAP"
    key = f"{project_id}:{scene.get('scene_id', index)}".encode("utf-8")
    digest = hashlib.sha256(key).digest()
    return INITIAL_CREDITS[int.from_bytes(digest[:2], "big") % len(INITIAL_CREDITS)]



def run(cmd, timeout=None):
    timeout = timeout or max(60, int(os.getenv("FFMPEG_TIMEOUT_SECONDS", "600")))
    print("+", " ".join(str(x) for x in cmd), flush=True)
    subprocess.run(cmd, check=True, timeout=timeout)


def media_duration(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path),
    ], text=True)
    return float(json.loads(out)["format"]["duration"])


def _font_path(bold=True):
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for value in candidates:
        if value and Path(value).is_file():
            return value
    raise RuntimeError("CJK font not found")


def _font(size: int, bold=True):
    return ImageFont.truetype(_font_path(bold), size)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    text = str(text or "").strip()
    if not text:
        return []
    lines = []
    current = ""
    for char in text:
        trial = current + char
        box = draw.textbbox((0, 0), trial, font=font)
        if current and box[2] - box[0] > max_width:
            lines.append(current)
            current = char
        else:
            current = trial
    if current:
        lines.append(current)
    return lines[:4]


def _overlay_png(scene: dict, output: Path, width: int, height: int):
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    text = str(scene.get("overlay_text") or "").strip()
    if text:
        size = max(36, int(min(width, height) * 0.058))
        font = _font(size, True)
        max_width = int(width * 0.84)
        lines = _wrap_text(draw, text, font, max_width)
        line_h = int(size * 1.35)
        box_h = line_h * len(lines) + int(size * 0.60)
        top = int(height * 0.07)
        left = int(width * 0.08)
        right = width - left
        draw.rounded_rectangle(
            (left, top, right, top + box_h),
            radius=max(12, size // 4),
            fill=(0, 0, 0, 142),
        )
        y = top + int(size * 0.25)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (width - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
            y += line_h

    credit = scene.get("photo_credit")
    if credit:
        credit = str(credit).strip()
        if credit:
            if not credit.lower().startswith("photo:"):
                credit = f"Photo: {credit}"
            size = max(20, int(min(width, height) * 0.026))
            font = _font(size, False)
            bbox = draw.textbbox((0, 0), credit, font=font)
            margin = int(min(width, height) * 0.025)
            x = width - (bbox[2] - bbox[0]) - margin
            y = height - (bbox[3] - bbox[1]) - margin
            draw.text((x + 2, y + 2), credit, font=font, fill=(0, 0, 0, 150))
            draw.text((x, y), credit, font=font, fill=(255, 255, 255, 220))

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "PNG")
    return output


def _sanitize_image(path: Path, output: Path, width: int, height: int):
    with Image.open(path) as source:
        source.load()
        source = ImageOps.exif_transpose(source).convert("RGB")
        contained = ImageOps.contain(source, (width, height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (width, height), "white")
        x = (width - contained.width) // 2
        y = (height - contained.height) // 2
        canvas.paste(contained, (x, y))
        canvas.save(output, "JPEG", quality=94, subsampling=0)
    return output


def _render_visual_scene(image: Path, overlay: Path, duration: float, output: Path,
                         width: int, height: int, fps: int, motion: str):
    duration = max(0.6, float(duration))
    fade = "0.22" if motion != "none" else "0.001"
    filter_complex = (
        f"[0:v]fps={fps},format=yuv420p[base];"
        f"[1:v]format=rgba,fade=t=in:st=0:d={fade}:alpha=1[ov];"
        f"[base][ov]overlay=0:0:format=auto,format=yuv420p[outv]"
    )
    run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image),
        "-loop", "1", "-i", str(overlay),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-t", f"{duration:.3f}",
        "-r", str(fps),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart",
        str(output),
    ])


def _concat_video_only(files: list[Path], output: Path):
    listing = output.with_suffix(".txt")
    listing.write_text("\n".join(f"file '{p.resolve()}'" for p in files), encoding="utf-8")
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(output),
    ])


def _mux(video: Path, audio: Path, output: Path, duration: float):
    run([
        "ffmpeg", "-y", "-i", str(video), "-i", str(audio),
        "-t", f"{duration:.3f}",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", str(output),
    ])


def _concat_av(files: list[Path], output: Path):
    listing = output.with_suffix(".txt")
    listing.write_text("\n".join(f"file '{p.resolve()}'" for p in files), encoding="utf-8")
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(output),
    ])


def _render_cta(output_dir: Path, width: int, height: int, fps: int, duration: float = 1.2) -> Path:
    image = output_dir / "cta_v2.png"
    clip = output_dir / "cta_v2.mp4"
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    title_size = max(38, int(min(width, height) * 0.070))
    sub_size = max(24, int(min(width, height) * 0.040))
    title_font = _font(title_size, True)
    sub_font = _font(sub_size, False)
    title = "WANKO SNAP"
    sub = "犬との暮らしを、もう少し深く。"
    for text, font, y in [
        (title, title_font, int(height * 0.43)),
        (sub, sub_font, int(height * 0.53)),
    ]:
        box = draw.textbbox((0, 0), text, font=font)
        x = (width - (box[2] - box[0])) // 2
        draw.text((x, y), text, font=font, fill=(24, 24, 24))
    canvas.save(image, "PNG")

    run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-t", f"{duration:.3f}",
        "-r", str(fps),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart", str(clip),
    ])
    return clip


def _speed_for(job: dict) -> float:
    voice = job.get("voice") or {}
    if voice.get("speed") is not None:
        return float(voice["speed"])
    if job["category"] == "long":
        return float(os.getenv("LONG_VOICE_SPEED_V2", DEFAULT_LONG_SPEED))
    if job["category"] == "news":
        return float(os.getenv("NEWS_VOICE_SPEED_V2", DEFAULT_NEWS_SPEED))
    return float(os.getenv("SHORT_VOICE_SPEED_V2", DEFAULT_SHORT_SPEED))


def _join_narration(texts: list[str]) -> str:
    result = []
    for text in texts:
        t = text.strip()
        if not t:
            continue
        if t[-1] not in "。！？!?":
            t += "。"
        result.append(t)
    return "".join(result)


def prepare_audio(job: dict, output_dir: Path, client: VoiceVoxClient,
                  strict_qc: bool = True) -> dict:
    shared = load_reading_map()
    speaker_id, speaker_label = client.choose_voice(job["project_id"], job.get("voice"))
    speed = _speed_for(job)
    groups = narration_groups(job)
    prepared = []
    all_risks = []

    for group_index, group in enumerate(groups, 1):
        scene_texts = []
        estimates = []
        for scene in group:
            text, risks = spoken_text(scene, shared)
            all_risks.extend(risks)
            scene_texts.append(text)
            estimates.append(client.estimate_seconds(text, speaker_id, speed))

        joined = _join_narration(scene_texts)
        audio = output_dir / f"group_{group_index:02d}.wav"
        client.synthesize(joined, audio, speaker_id, speed)
        actual = media_duration(audio)
        estimate_sum = max(0.01, sum(estimates))
        durations = [max(0.6, actual * (estimate / estimate_sum)) for estimate in estimates]
        correction = actual / max(0.01, sum(durations))
        durations = [x * correction for x in durations]
        prepared.append({
            "scenes": group,
            "audio": audio,
            "duration": actual,
            "scene_durations": durations,
        })

    pronunciation_result = pronunciation_qc(all_risks)
    total = sum(x["duration"] for x in prepared)
    duration_result = duration_qc(job, total)

    if strict_qc and not pronunciation_result.ok:
        raise RuntimeError("; ".join(pronunciation_result.reasons))
    if strict_qc and not duration_result.ok:
        raise RuntimeError("; ".join(duration_result.reasons))

    return {
        "speaker_id": speaker_id,
        "speaker_label": speaker_label,
        "speed": speed,
        "groups": prepared,
        "total_narration_seconds": total,
        "pronunciation_qc": pronunciation_result.to_dict(),
        "duration_qc": duration_result.to_dict(),
    }


def render_job(job: dict, job_dir: Path, output_dir: Path,
               strict_qc: bool = True, preflight_only: bool = False) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    width = int(job["video"]["width"])
    height = int(job["video"]["height"])
    fps = int(job["video"]["fps"])

    client = VoiceVoxClient()
    client.wait_ready()
    audio_plan = prepare_audio(job, output_dir, client, strict_qc=strict_qc)

    result = {
        "project_id": job["project_id"],
        "speaker": audio_plan["speaker_label"],
        "voice_speed": audio_plan["speed"],
        "total_narration_seconds": round(audio_plan["total_narration_seconds"], 2),
        "pronunciation_qc": audio_plan["pronunciation_qc"],
        "duration_qc": audio_plan["duration_qc"],
        "preflight_only": preflight_only,
    }

    if preflight_only:
        return result

    rendered_groups = []
    scene_counter = 0

    for group_index, plan in enumerate(audio_plan["groups"], 1):
        visual_clips = []
        for scene, duration in zip(plan["scenes"], plan["scene_durations"]):
            scene_counter += 1
            sanitized = output_dir / f"image_{scene_counter:03d}.jpg"
            overlay = output_dir / f"overlay_{scene_counter:03d}.png"
            clip = output_dir / f"visual_{scene_counter:03d}.mp4"

            _sanitize_image(job_dir / scene["image"], sanitized, width, height)
            display_scene = dict(scene)
            display_scene["photo_credit"] = _resolve_photo_credit(job["project_id"], scene, scene_counter)
            _overlay_png(display_scene, overlay, width, height)
            _render_visual_scene(
                sanitized,
                overlay,
                duration,
                clip,
                width,
                height,
                fps,
                scene.get("motion") or "fade_text",
            )
            visual_clips.append(clip)

        visual_group = output_dir / f"group_{group_index:02d}_visual.mp4"
        group_clip = output_dir / f"group_{group_index:02d}_final.mp4"
        _concat_video_only(visual_clips, visual_group)
        _mux(visual_group, plan["audio"], group_clip, plan["duration"])
        rendered_groups.append(group_clip)

    if job.get("append_common_cta") and job["format"] == "short":
        rendered_groups.append(_render_cta(output_dir, width, height, fps))

    final = output_dir / "final.mp4"
    _concat_av(rendered_groups, final)
    result["video_path"] = str(final)
    result["rendered_duration_seconds"] = round(media_duration(final), 2)
    return result
