# Flash Neo — Multi-User Static-IP Relay (Render + StaticIP.in)

Deploy this relay **once** on Render (Free Tier). Every Flash Neo user on `flashneo.pages.dev` can then paste their own **StaticIP.in Proxy URL** (`http://user:pass@ip:port`) inside the app and trade directly from mobile — no PC, no Termux, and no VPS needed for users.

## Quick Render Deploy
1. Push the files inside `flash_neo_relay/` to a new GitHub repository.
2. In **Render Dashboard**, click **New → Web Service**, connect that repo:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn relay:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** Free
3. Copy your live Render URL (e.g. `https://flash-neo-relay.onrender.com`).
4. In **Cloudflare Pages** (`flashneo` project) → **Settings → Environment Variables**, add:
   - `RELAY_URL` = `https://flash-neo-relay.onrender.com`
   - *(Optional)* `RELAY_SECRET` = same random string added in Render Environment Variables.
5. Re-upload the updated `flash_neo_cf_direct.zip` to Cloudflare Pages.

## Security
- Strictly allowlists only `*.kotaksecurities.com`, `*.kotakneo.com`, `api4.ipify.org`, and `api6.ipify.org`.
- Stores zero user credentials, sessions, or proxy passwords on the server.
