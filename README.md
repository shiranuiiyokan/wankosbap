# Public video render worker

This public repository is used only for generic, non-sensitive video rendering.

It must not contain:
- Google Drive IDs that reveal private structure
- Production Queue contents
- YouTube OAuth tokens or refresh tokens
- service-account JSON
- private project data or manifests

Credentials, when the full worker is enabled, must be stored only in GitHub Actions Secrets.

Current state: smoke-test only. It verifies that a public GitHub-hosted runner can start VOICEVOX, run FFmpeg, and create a small video without using the private dog-video-maker repository.
