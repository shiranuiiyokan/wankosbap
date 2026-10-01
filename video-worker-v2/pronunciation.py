import json
import re
from pathlib import Path

DEFAULT_MAP_PATH = Path(__file__).parent / "voice_reading_map.json"

_LATIN_TOKEN = re.compile(r"(?<![A-Za-z0-9._-])[A-Za-z][A-Za-z0-9._-]*(?![A-Za-z0-9._-])")
_NUMBER_UNIT = re.compile(r"\d+(?:[.,]\d+)?\s*(?:cm|mm|kg|g|ml|L|％|%|歳|回|頭|匹|分|秒|年|月|日)", re.IGNORECASE)
_RISK_SYMBOLS = re.compile(r"[×/／+＋&＆]")


def load_reading_map(path: Path | None = None) -> dict[str, str]:
    path = path or DEFAULT_MAP_PATH
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("reading map must be a JSON object")
    return {str(k): str(v) for k, v in data.items() if str(k).strip()}


def normalize_tts_text(text: str) -> str:
    """Remove visual Japanese spacing without destroying normal Latin spacing."""
    text = str(text or "").replace("・", "")
    jp = "\u3040-\u30ff\u3400-\u9fff々〆ヵヶー"
    text = re.sub(rf"(?<=[{jp}])\s+", "", text)
    text = re.sub(rf"\s+(?=[{jp}、。！？])", "", text)
    text = re.sub(r"[ \t]+([、。！？])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def apply_readings(text: str, shared: dict[str, str] | None = None,
                   local: dict[str, str] | None = None) -> str:
    merged: dict[str, str] = {}
    merged.update(shared or {})
    merged.update(local or {})
    spoken = str(text or "")
    for source in sorted(merged, key=len, reverse=True):
        spoken = spoken.replace(source, merged[source])
    return normalize_tts_text(spoken)


def unresolved_risks(text: str, known_sources: set[str] | None = None) -> list[str]:
    """Find tokens likely to be misread before TTS. This is intentionally conservative."""
    known_sources = known_sources or set()
    risks: list[str] = []
    for token in _LATIN_TOKEN.findall(str(text or "")):
        if token not in known_sources:
            risks.append(token)
    for token in _NUMBER_UNIT.findall(str(text or "")):
        if token not in known_sources and not any(token.endswith(k) for k in known_sources):
            risks.append(token)
    for token in _RISK_SYMBOLS.findall(str(text or "")):
        if token not in known_sources:
            risks.append(token)
    return sorted(set(risks))


def spoken_text(scene: dict, shared_map: dict[str, str]) -> tuple[str, list[str]]:
    narration = str(scene.get("narration") or "").strip()
    if not narration:
        return "", []

    local = scene.get("pronunciation") or {}
    if not isinstance(local, dict):
        local = {}

    # Legacy narration_reading is ignored by default. v2 uses explicit term mappings,
    # because full-sentence reading overrides made maintenance and QC unreliable.
    if scene.get("use_legacy_narration_reading"):
        legacy = str(scene.get("narration_reading") or "").strip()
        if legacy:
            narration = legacy

    known = set(shared_map) | set(local)
    risks = unresolved_risks(narration, known)
    return apply_readings(narration, shared_map, local), risks
