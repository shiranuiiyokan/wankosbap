# Video Worker v2 rollout state

Updated: 2026-10-02 JST

## Live state

v1 remains the fallback/majority production path.

DOG is now blue-green:
- v2: max 1 DOG/day, scheduled 20:55 JST, publish slot 09:30 JST
- v1: max 2 DOG/day, publish slots 13:00 / 19:00 JST
- v2 and v1 use separate Drive source lanes, so they cannot claim the same folder

MBTI, cat_other, news and long remain on v1.

The source-production Scheduled Task is responsible for writing exactly one selected DOG/day into the v2 DOG lane and the other two DOGs into the legacy lane. It must never duplicate a project_id across lanes.

## Why this is staged

The old system had several real failure modes:
- TTS prosody reset at every visual scene
- fixed 0.55s scene-tail pauses
- full-sentence narration_reading could make speech fragile
- Shorts source content was often materially shorter than intended
- long-form duration estimates were optimistic and the 15-minute gate ran only after expensive rendering
- Drive service-account file creation caused storage/ownership failures
- GitHub generated-media artifacts previously exhausted artifact storage

v2 addresses these without replacing the live worker all at once.

## Canary acceptance criteria

Do not expand the v2 share until all of the following are true for at least 3 consecutive scheduled DOG canaries:

1. Upload/schedule succeeds and the source folder is moved to v2 done exactly once.
2. No duplicate YouTube video and no duplicate project_id across v1/v2.
3. Pronunciation QC has zero unresolved risks.
4. Measured narration is within the 42–58s Shorts target before CTA.
5. No missing image / manifest path mismatch.
6. v1 13:00 and 19:00 DOG production continues normally.
7. No generated-media GitHub artifact or cache is created.
8. Runner free-disk guard passes.
9. No Drive file-creation attempt is made by the service account; v2 only renames/moves existing source folders.
10. No paid API/service is required.

If a canary fails duration QC, source automation repairs the same folder with meaningful narration and does not create a replacement v2 project. If pronunciation QC fails, source automation repairs term-level pronunciation mappings. The failed project is not silently sent through v1.

## Promotion order

After the initial DOG canary criteria are met:
1. Expand DOG to v2 gradually.
2. Move MBTI next.
3. Move cat_other after MBTI is stable.
4. Keep news on the proven fast lane until v2 immediate-publication behavior is separately tested.
5. Move long last, only after source narration routinely clears real TTS >=900s before visual rendering.

The richer B+C visual layer (card reveals, comparison-step reveals, chapter transitions, optional alternative free TTS engines) is added after the continuous-audio A+B path is stable. Photo zoom/pan remains disabled.

## Capacity rules

- GitHub Actions generated-media artifacts: 0
- GitHub generated-media cache: 0
- local WAV/MP4: ephemeral runner files, deleted after processing
- v2 max uploads per scheduled canary run: 1
- final full-production target remains well below the current YouTube videos.insert default daily bucket
- source files live in Drive; worker does not upload final MP4 back to Drive
- failures are isolated per project and must not halt unrelated categories

## Current v2 Drive lanes

- root: `1bBDC_u7AknZRT9KcK93FwI0FL2xuUoQd`
- dog: `1-rXG54yNISgX7Sx69y2qlg40LsIakBat`
- mbti: `1aRZgjrmj_MxmbhraK_Yi-bJJFEfTrrdp`
- cat_other: `1gqijyx4n9EVZwXD13sTVlGVv0CQjv6ua`
- news: `1toNSuGd8bVrZB0DOXm0kFtuXVIBjn6l1`
- long: `1O3hAUmh-9Afp2aX_aaHQQkViG_8CRtSe`
- done: `1fa3JmVUETnLEVJKf7kjXL4UZixgpI5ng`
- error: `1urPnVZY6_qcjANd-bJYv1rWTfXX9e0DO`
