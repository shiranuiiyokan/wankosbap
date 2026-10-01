from __future__ import annotations

from pathlib import Path

SHORT_MIN_SECONDS = 42.0
SHORT_MAX_SECONDS = 58.0
LONG_MIN_SECONDS = 900.0


def _existing_image(job_dir: Path, image: str) -> Path:
    candidate = job_dir / image
    if candidate.is_file():
        return candidate
    name = Path(image).name
    root_candidate = job_dir / name
    if root_candidate.is_file():
        return root_candidate
    images_candidate = job_dir / "images" / name
    if images_candidate.is_file():
        return images_candidate
    raise FileNotFoundError(f"scene image not found: {image}")


def normalize_manifest(raw: dict, category: str, job_dir: Path, validate_images: bool = True) -> dict:
    project_id = str(raw.get("project_id") or raw.get("企画ID") or raw.get("job_id") or job_dir.name)
    title = str(raw.get("title") or (raw.get("youtube") or {}).get("title") or project_id)
    video = dict(raw.get("video") or {})
    is_long = category == "long" or str(raw.get("format", "")).lower() == "long"

    width = int(video.get("width") or (1920 if is_long else 1080))
    height = int(video.get("height") or (1080 if is_long else 1920))
    fps = int(video.get("fps") or 30)

    raw_scenes = raw.get("scenes") or []
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ValueError("manifest requires non-empty scenes")

    scenes = []
    for idx, source in enumerate(raw_scenes, 1):
        if isinstance(source, str):
            source = {"image": source}
        image = str(source.get("image") or "").strip()
        if not image:
            raise ValueError(f"scene {idx} missing image")
        resolved = _existing_image(job_dir, image) if validate_images else Path(image)
        narration = str(source.get("narration") or source.get("voice") or "").strip()
        if not narration:
            raise ValueError(f"scene {idx} missing narration")

        item = {
            "scene_id": str(source.get("scene_id") or f"{idx:02d}"),
            "image": str(resolved.relative_to(job_dir)) if validate_images else image,
            "narration": narration,
            "overlay_text": str(source.get("overlay_text") or source.get("on_screen_text") or "").strip(),
            "chapter": str(source.get("chapter") or "main").strip() or "main",
            "duration_hint": source.get("duration_seconds", source.get("duration")),
            "style_role": str(source.get("style_role") or source.get("image_format") or "auto"),
            "motion": str(source.get("motion") or "fade_text"),
            "photo_credit": source.get("photo_credit") if source.get("photo_credit") is not None else (
                "auto" if source.get("photo_credit_mode") == "auto" else None
            ),
            "dog_camera_gaze": bool(source.get("dog_camera_gaze", False)),
            "pronunciation": source.get("pronunciation") or {},
        }
        if source.get("narration_reading"):
            item["narration_reading"] = source["narration_reading"]
        if source.get("use_legacy_narration_reading"):
            item["use_legacy_narration_reading"] = True
        scenes.append(item)

    voice = dict(raw.get("voice") or {})
    if raw.get("voicevox_speed") is not None and voice.get("speed") is None:
        voice["speed"] = raw.get("voicevox_speed")

    return {
        "schema_version": 2,
        "project_id": project_id,
        "category": category,
        "format": "long" if is_long else "short",
        "title": title,
        "description": str(raw.get("description") or (raw.get("youtube") or {}).get("description") or ""),
        "youtube": dict(raw.get("youtube") or {}),
        "video": {"width": width, "height": height, "fps": fps},
        "voice": voice,
        "scenes": scenes,
        "append_common_cta": bool(raw.get("append_common_cta", not is_long and category != "news")),
        "quality": {
            "short_min_seconds": float((raw.get("quality") or {}).get("short_min_seconds", SHORT_MIN_SECONDS)),
            "short_max_seconds": float((raw.get("quality") or {}).get("short_max_seconds", SHORT_MAX_SECONDS)),
            "long_min_seconds": float((raw.get("quality") or {}).get("long_min_seconds", LONG_MIN_SECONDS)),
        },
    }


def narration_groups(job: dict) -> list[list[dict]]:
    scenes = job["scenes"]
    if job["format"] == "short":
        return [scenes]

    groups: list[list[dict]] = []
    current_key = None
    current: list[dict] = []
    for scene in scenes:
        key = scene.get("chapter") or "main"
        if current and key != current_key:
            groups.append(current)
            current = []
        current_key = key
        current.append(scene)
    if current:
        groups.append(current)
    return groups
