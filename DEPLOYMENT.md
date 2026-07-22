# Deploying ClauseGuard — Step by Step, No Jargon

This gets you a real, live website with a working backend, using only free
accounts. It takes about 30-45 minutes the first time. Every step below
has been checked against this exact codebase — the config files it tells
you to use already exist in this zip.

**The shape of it:** your website (frontend) lives on Vercel. Your server
(backend) lives on Render. Your database lives on Neon. Your uploaded
files live on Cloudflare R2. All four are separate free accounts, all four
talk to each other over the internet. This is completely normal — almost
every real production app is built this way, not as one single "thing."

---

## Part 0 — What you need before starting

Five free accounts. None need a credit card except optionally Stripe (and
even that's free in test mode):

1. A [GitHub](https://github.com) account — to hold your code.
2. A [Render](https://render.com) account — runs your backend server.
3. A [Vercel](https://vercel.com) account — runs your website.
4. A [Neon](https://neon.tech) account — your database.
5. A [Cloudflare](https://cloudflare.com) account — where uploaded
   contracts get stored.
6. A [Groq](https://console.groq.com) account — the free AI that reads
   the contracts. No credit card.

Sign up for all six now with the same email if you want — takes five
minutes, and you'll need them all anyway.

---

## Part 1 — Put your code on GitHub

1. Go to [github.com/new](https://github.com/new), create a new repository.
   Name it whatever you want (e.g. `clauseguard`). Leave it empty — don't
   add a README or .gitignore, you already have those.
2. On your own computer, unzip this project and open a terminal inside
   the `clauseguard` folder.
3. Run these commands one at a time:
   ```bash
   git init
   git add -A
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git
   git push -u origin main
   ```
4. Refresh your GitHub page — your code should now be there.

*(This exact `.gitignore` setup was tested by literally running these
commands and checking nothing sensitive got uploaded — no passwords, no
`.env` files, no database files. 123 files went up, all of them meant to.)*

---

## Part 2 — Set up your database (Neon)

1. Log into Neon, click **New Project**. Any name, any region close to you.
2. On the project page, find the **Connection String**. Neon shows one
   that looks like:
   `postgresql://user:password@ep-something-pooler.region.aws.neon.tech/neondb?sslmode=require&channel_binding=require`
3. Copy it somewhere safe. **One small edit before you use it**: change
   `postgresql://` at the very start to `postgresql+asyncpg://` — same
   string, just that one word changes. That's genuinely the only manual
   edit needed.

   You do **not** need to remove `?sslmode=require&channel_binding=require`
   yourself, and you don't need to switch to a non-pooled connection
   string either — this backend detects and correctly handles both of
   those automatically (`app/database.py`, tested in
   `backend/tests/test_database_pooler_fix.py`). Earlier drafts of this
   guide didn't mention this and would have sent you straight into a
   `TypeError` — fixed at the code level instead of asking you to
   hand-edit connection strings correctly, which isn't a reasonable thing
   to expect anyone to get right by hand.

That's the whole database step. Neon's free tier doesn't expire and
doesn't need a credit card.

---

## Part 3 — Set up file storage (Cloudflare R2)

This is where uploaded contracts get saved so they don't disappear.

1. Log into Cloudflare, go to **R2** in the left sidebar (you may need to
   click "Get Started" once — still free, no card needed for the free tier).
2. Click **Create bucket**. Name it `clauseguard-uploads` (or anything).
3. Go to **Manage R2 API Tokens** (usually a link on the R2 overview page)
   and create a new API token. Give it **Object Read & Write** permission,
   scoped to your new bucket.
4. It will show you three things — copy all three somewhere safe:
   - **Access Key ID**
   - **Secret Access Key**
   - Your **Account ID** (shown on the main R2 page, top right area)
5. Your storage endpoint URL is:
   `https://<your-account-id>.r2.cloudflarestorage.com`

You now have five things written down: connection string (Part 2), bucket
name, endpoint URL, access key, secret key.

---

## Part 4 — Get your free AI key (Groq)

1. Log into [console.groq.com](https://console.groq.com/keys).
2. Click **Create API Key**. Copy it — it starts with `gsk_`.

No credit card, no trial period. This is what actually reads and scores
the contracts.

---

## Part 5 — Deploy the backend (Render)

1. Log into Render, click **New +** → **Blueprint**.
2. Connect your GitHub account if you haven't, and pick the repository
   you pushed in Part 1.
3. Render will find the `render.yaml` file already in this project (in
   the `backend` folder) and read it automatically — it'll show you a
   list of settings it wants filled in.
4. Fill in each blank value it asks for, using what you collected above:

   | Setting | What to put |
   |---|---|
   | `GROQ_API_KEY` | your `gsk_...` key from Part 4 |
   | `DATABASE_URL` | your Neon connection string from Part 2 (with `+asyncpg` added) |
   | `S3_BUCKET` | the bucket name you picked in Part 3 |
   | `S3_ENDPOINT_URL` | your R2 endpoint URL from Part 3 |
   | `S3_ACCESS_KEY_ID` | from Part 3 |
   | `S3_SECRET_ACCESS_KEY` | from Part 3 |
   | `FRONTEND_URL` | leave blank for now, you'll fill this in Part 7 |
   | Stripe fields | leave blank unless you're setting up payments today |

5. Click **Apply** / **Deploy**. Render will build and start your backend
   — takes 3-5 minutes the first time.
6. When it's done, Render shows you a URL like
   `https://clauseguard-backend-xyz.onrender.com`. **Copy this URL** —
   you need it in the next step.
7. Check it actually works: open `https://your-url.onrender.com/health`
   in a browser. You should see `{"status":"ok"}`. If you see that, your
   entire backend — database, storage, AI — is live.

**One real thing to know:** Render's free tier "falls asleep" after 15
minutes of no traffic, and takes about 30-60 seconds to wake back up on
the next request. Totally normal for a free tier. If you outgrow that,
Render's paid tier removes it.

---

## Part 6 — Deploy the website (Vercel)

1. Log into Vercel, click **Add New** → **Project**.
2. Import the same GitHub repository.
3. Vercel will ask for a **Root Directory** — click Edit and set it to
   `frontend`. This is the one setting that's easy to miss.
4. It should auto-detect "Vite" as the framework. Leave build settings on
   their defaults.
5. Before deploying, expand **Environment Variables** and add one:
   - Name: `VITE_API_URL`
   - Value: the Render URL from Part 5, e.g.
     `https://clauseguard-backend-xyz.onrender.com` (no trailing slash)
6. Click **Deploy**. Takes about a minute.
7. When it's done, Vercel gives you a URL like
   `https://clauseguard-yourname.vercel.app`. Open it — you should see
   the real landing page.

---

## Part 7 — Connect the last wire

Your backend needs to know your website's URL too (for password reset
links and Stripe redirects to work correctly):

1. Go back to Render → your backend service → **Environment**.
2. Set `FRONTEND_URL` to your Vercel URL from Part 6.
3. Render will automatically redeploy with the new setting (takes ~1 min).

---

## Part 8 — Actually test it

1. Open your Vercel URL.
2. Click **Get started**, create an account with a real email + password.
3. You should land on the dashboard.
4. Upload a PDF or DOCX contract. Watch it go from "Queued" to
   "Analyzing…" to "Complete."
5. Click into it — you should see real risk scores and explanations,
   generated by the actual Groq AI reading your actual document.

If that works end to end, you have a genuinely live, working product —
not a demo, not a mockup. Real database, real file storage, real AI.

---

## Optional: Part 9 — Payments (Stripe)

Only do this if you actually want to charge people. Stripe's test mode is
free and needs no bank details, so you can try this risk-free:

1. Create a Stripe account, make sure you're in **Test mode** (toggle in
   the dashboard).
2. Get your test secret key from **Developers → API keys**.
3. Create two products under **Product catalog** — call them Starter and
   Pro — each with a recurring monthly price. Copy each price's ID
   (starts with `price_`).
4. Back in Render, set:
   - `STRIPE_SECRET_KEY` → your test key
   - `STRIPE_PRICE_STARTER` / `STRIPE_PRICE_PRO` → the two price IDs
5. For webhooks (so Stripe can tell your backend when someone pays), the
   simplest path is the Stripe CLI on your own computer:
   `stripe listen --forward-to https://your-render-url.onrender.com/api/billing/webhook`
   — it prints a webhook secret, put that in Render's `STRIPE_WEBHOOK_SECRET`.
6. Test with card number `4242 4242 4242 4242`, any future date, any CVC.
   No real money moves in test mode, ever.

---

## If something doesn't work

- **Backend URL shows an error, not `{"status":"ok"}`** → check Render's
  **Logs** tab for the actual error. Usually a typo in one of the
  environment variables.
- **Website loads but login/upload does nothing** → open your browser's
  developer console (F12) and check for a red error mentioning
  `VITE_API_URL` or a network failure — usually means that variable is
  missing or has the wrong URL in Vercel's settings.
- **Upload succeeds but analysis never finishes** → almost always means
  `GROQ_API_KEY` is missing or wrong in Render.
- **Files or account data disappearing after a while** → means Part 2 or
  Part 3 wasn't actually completed and it's silently using local storage
  instead — double check `DATABASE_URL` and `STORAGE_BACKEND=s3` are both
  really set in Render's environment variables.

You now have four dashboards worth bookmarking: Render (backend + logs),
Vercel (website + deploys), Neon (database), Cloudflare (files). That's
genuinely what "production" looks like for a project this size — not
one button, four small, honest pieces.
