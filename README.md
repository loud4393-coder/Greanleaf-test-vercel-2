# Greenleaf Mini App — release candidate

## Vercel environment variables
Set these in **Vercel → Project → Settings → Environment Variables** for Production and Preview as needed:

- `DATABASE_URL` — Neon PostgreSQL connection string.
- `BOT_TOKEN` — Telegram bot token; used to validate Telegram Web App `initData` and send order alerts.
- `ADMIN_ID` — numeric Telegram user ID of the store owner.
- `BLOB_READ_WRITE_TOKEN` — Vercel Blob read/write token.

Never commit real secrets or share them in chat.

## Deploy
Keep the existing `vercel.json` from your repository unchanged. This package intentionally does not include it. Vercel should deploy the Python Flask entry point at `app.py` and serve `static/` assets.

## First request / database
The app creates its PostgreSQL tables on the first request for each serverless instance. `app_meta` guards the one-time removal of the three legacy demo name/price pairs and one-time insertion of three sample products. Review the cleanup block in `app.py` before first deployment if those exact name/price pairs could represent real merchandise. Sample products are created once; deleting them later does not cause them to be reinserted.

## Blob image uploads
The backend uploads JPEG, PNG, and WEBP images through Vercel Blob's REST endpoint. The frontend compresses selected images before upload; the backend enforces request and image-size limits. `BLOB_READ_WRITE_TOKEN` must belong to the Blob store connected to this Vercel project.

## Telegram admin access
Open the Mini App from its Telegram bot button so Telegram supplies signed `initData`. The server verifies the signature and checks that the user ID matches `ADMIN_ID`. Opening the raw Vercel URL does not grant owner access.

## Included features
- PostgreSQL-backed product catalog and orders
- Owner-only product create/edit/soft-delete
- Product photos in Vercel Blob
- Order archive and status updates
- Telegram order notifications
- Product comments and related products
- Russian / Turkmen UI and mobile layout

## Verification boundary
Local syntax and static consistency checks can be run before deployment. Live Neon, Blob, and Telegram behavior still needs a deployment test using your project's configured environment variables; never put those secret values into the repository.
