# Greenleaf Vercel Test

Minimal Flask deployment test.

Expected:
- `/` → GREENLEAF TEST OK
- `/health` → JSON with status `ok`
- `/api/test` → JSON with status `ok`

This deliberately contains no database, Telegram bot, authentication, uploads, admin panel, Procfile, or old Greenleaf code.

For Vercel, import the repository and deploy with the default settings. No secrets or environment variables are needed for this test.
