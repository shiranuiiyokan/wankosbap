# Video worker

This folder contains the generic public rendering worker.

The worker code contains no Google Drive folder IDs, OAuth tokens, service-account keys, Production Queue data, or private manifests. Runtime credentials are read from GitHub Actions Secrets only.

## Required repository secrets

- GOOGLE_SERVICE_ACCOUNT_JSON
- YOUTUBE_CLIENT_ID
- YOUTUBE_CLIENT_SECRET
- YOUTUBE_REFRESH_TOKEN
- SCHEDULED_DOG_FOLDER_ID
- SCHEDULED_MBTI_FOLDER_ID
- SCHEDULED_CAT_FOLDER_ID
- SCHEDULED_LONG_FOLDER_ID
- SCHEDULED_DONE_FOLDER_ID
- SCHEDULED_ERROR_FOLDER_ID

Until those secrets exist, the production workflow stays manual-only. Pushes only run a syntax validation job.

After credentials are installed and a dry run succeeds, the workflow can be switched to one scheduled batch per day.
