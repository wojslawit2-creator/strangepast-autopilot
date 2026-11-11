# Strange Past autopilot

Twice a day GitHub Actions writes a weird-history script (checked against Wikipedia),
records an AI voice-over, generates AI images, renders a 1080x1920 reel with captions
and publishes it to Instagram (@strangepast.daily) and TikTok.

## Secrets (Settings → Secrets and variables → Actions)
| Name | What |
|---|---|
| `IG_ACCESS_TOKEN` | Instagram long-lived token (Instagram API with Instagram Login) |
| `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN` | TikTok Content Posting API app |
| `GH_PAT` | fine-grained token with *Secrets: read & write* on this repo (rotates tokens) |
| `GEMINI_API_KEY` | optional, free key from aistudio.google.com (better scripts) |

Variable `TIKTOK_MODE`: `inbox` (default, drafts in the TikTok app) or `direct` (after TikTok audit).

Test: Actions → Strange Past autopilot → Run workflow (dry run) → download the `reel` artifact.
