# Video Worker v2 — parallel shadow pipeline

This directory is intentionally isolated from `video-worker/`.
The production workflow continues to use the existing worker unchanged.

## Non-negotiable requirements

- Additional recurring cost: **0**
- Daily operation: **fully automatic**
- User PC: **not required / not always-on**
- Production must not depend on GitHub Actions artifacts or caches for generated media
- Generated WAV/MP4 files are ephemeral on the runner and deleted after each shadow job
- Google Drive remains the source-of-truth for scheduled assets; v2 shadow mode performs **no Drive writes**
- Images themselves do not zoom or pan. Motion is limited to readable information layers.
- People shown in generated visual plans are Japanese adults. "Gap/candid attraction" styling is only for 20+ adults and only when appropriate to the topic.
- Pronunciation errors are treated as a quality failure.

## Core change

v1 couples one image scene to one TTS request.

v2 separates:
- narration timeline
- visual timeline

Shorts synthesize narration as one continuous audio block.
Long-form videos synthesize one continuous block per contiguous chapter.
Per-scene timing is estimated from VOICEVOX audio-query phoneme lengths, then normalized to the final synthesized block duration.

This removes the fixed per-scene 0.55s tail and prevents prosody from resetting on every image cut.

## Duration policy

- Shorts target: 42–58 seconds
- Long-form minimum target: 900 seconds
- Duration QC happens after audio preflight and **before expensive video rendering**
- Strict mode blocks rendering when duration or pronunciation QC fails
- Shadow mode defaults to non-strict so old assets can be measured without altering production

## Pronunciation policy

`narration` stays normal Japanese text.
`narration_reading` is not automatically preferred.

Readings are applied using:
1. shared `voice_reading_map.json`
2. per-scene `pronunciation` dictionary

Unknown Latin tokens, number+unit patterns, and risky symbols are surfaced before TTS.
The correct fix is a term-level pronunciation mapping, not full hiragana conversion.

## Visual motion

The source image is static.
Overlay text may fade in briefly. No zoom/pan is applied to photos.

Future v2/C work can add timeline-driven cards, underline strokes, comparison reveals, and chapter transitions while preserving text readability.

## Natural-photo credit

Future v2 manifests may specify `photo_credit: "WANKO SNAP"` or a neutral initial such as `M.K.`.
The renderer displays it as `Photo: ...` in the lower-right corner.

It is optional and only for suitable natural-photo scenes.
Dog-camera-eye-contact scenes may prefer `WANKO SNAP`; other candid scenes may use varied neutral initials.
Existing v1 assets do not receive invented credits automatically.

## Voice rotation

Until a preference emerges, v2 chooses a stable voice per project from a free VOICEVOX rotation.
The selected voice and speed are logged with each shadow result so performance can later be compared.
No paid TTS API is required.

## Storage safety

- No workflow artifacts
- No generated-media cache
- Runner free-space guard before work starts
- No finished MP4 upload back to Drive in shadow mode
- Work/output directories are deleted in `finally`
- Drive quota is logged for diagnosis
- Production v1 remains untouched

## Shadow defaults

- `V2_CATEGORY=dog`
- `V2_PREFLIGHT_ONLY=true`
- `V2_STRICT_QC=false`
- `V2_PROJECT_FILTER=` optional
- `V2_MIN_FREE_GB=4`

Shadow mode never uploads to YouTube and never moves, renames, or writes Drive files.
