# Video worker

This folder contains the generic public rendering worker.

The worker code contains no Google Drive folder IDs, OAuth tokens, service-account keys, Production Queue data, or private manifests. Runtime credentials are read from GitHub Actions Secrets only.

## Required repository secrets

- GOOGLE_SERVICE_ACCOUNT_JSON
- YOUTUBE_CLIENT_ID
- YOUTUBE_CLIENT_SECRET
- YOUTUBE_REFRESH_TOKEN

The Google Drive folder IDs are non-credential identifiers and are configured in the workflow. Until the four credentials above exist, the production workflow stays manual-only. Pushes only run a syntax validation job.

After credentials are installed and a dry run succeeds, the workflow can be switched to one scheduled batch per day.


## Current production architecture

This public worker is the production path. It reads scheduled assets from Google Drive,
renders them with VOICEVOX + FFmpeg, uploads the finished video directly to YouTube,
then moves the existing Drive job folder to done.

Required repository secrets:
- GOOGLE_SERVICE_ACCOUNT_JSON
- YOUTUBE_CLIENT_ID
- YOUTUBE_CLIENT_SECRET
- YOUTUBE_REFRESH_TOKEN

Security constraints:
- repository token permission is contents: read
- production runs only on schedule or manual dispatch
- pull_request_target is not used
- no finished video artifact is retained in normal production
- OAuth secrets are read only from GitHub Actions Secrets
- the YouTube OAuth scope remains youtube.upload only

The daily production schedule is 21:00 JST. If any required secret is missing, the credential
gate skips production before the expensive render job starts.
