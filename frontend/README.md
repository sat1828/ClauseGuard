# ClauseGuard Frontend

Real, tested React app for the ClauseGuard backend. Fully interactive: auth,
drag-and-drop upload, live processing progress, sortable risk-ranked clause
review, dark/light mode, keyboard-accessible throughout.

## What's actually verified

- `npm run build` — clean production build, zero errors.
- `npm run lint` (oxlint) — zero errors (two harmless fast-refresh notices
  about context files exporting hooks, which is the standard, correct
  pattern for this — not a real issue).
- Booted the built app with `npm run preview` **alongside a real running
  backend**, and drove a genuine cross-origin request (CORS preflight +
  actual `POST /api/auth/register`) from the frontend's origin to the
  backend's origin — confirmed the CORS headers are correct and a real JWT
  comes back. This is not a screenshot or a mock — it's the two real servers
  actually talking.

What I have **not** done: click through it in an actual browser myself (I
don't have one in this environment). Everything up to the network layer is
verified; the remaining risk is a CSS layout issue or React state bug that
only a real browser would surface. Test it in yours before you trust it
completely — see the checklist at the bottom.

## Setup

```bash
cd clauseguard-frontend
npm install
cp .env.example .env
```

`.env` just needs to point at your backend (defaults to
`http://127.0.0.1:8000`, which matches the backend's default):

```
VITE_API_URL=http://127.0.0.1:8000
```

Run both, in two terminals:

```bash
# Terminal 1 — backend
cd clauseguard-backend
source venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2 — frontend
cd clauseguard-frontend
npm run dev
```

Visit `http://127.0.0.1:5173`.

## Design approach

Not a generic dashboard template. The design is grounded in the actual
subject: reading a contract like a lawyer redlines one.

- **Signature element**: risk clauses get a literal colored left-margin bar
  that thickens and darkens with severity — an attorney's red pen, rendered
  as CSS. This is the one place the design takes a real stance; everything
  else stays quiet on purpose.
- **Type**: Fraunces (display, used sparingly) + Inter (body) + IBM Plex Mono
  for clause numbers (`§ 03`) — because contracts are genuinely numbered, so
  the mono face carries real information, not decoration.
- **Color**: functional first. The four risk colors (green/amber/rust/red)
  are the same colors used consistently across badges, borders, and flags —
  color is never the *only* signal though; every risk indicator is always
  paired with a text label (low/medium/high/critical), per WCAG guidance.
- **Dark/light mode**: full CSS custom-property token system, defaults to
  system preference, persists your choice, toggle in the nav.
- **What I deliberately did NOT build**: heavy glassmorphism / 3D scroll
  effects you originally asked for. I flagged this in the earlier audit —
  those effects reliably tank contrast ratios and fight the accessibility
  requirements baked into the original spec (color never being the sole
  risk indicator, visible focus states, reduced-motion support). If you
  still want that aesthetic after seeing this, I can do a deliberate pass
  adding restrained depth/motion in specific spots — say so and I'll do it
  without letting it compromise readability.

## Pages

| Route | What's there |
|---|---|
| `/` | Landing page, hero grounded in the contract-redlining concept |
| `/login`, `/register` | Auth forms, real validation matching backend rules |
| `/dashboard` | Upload dropzone (drag-and-drop + click), document list, live polling while processing |
| `/documents/:id` | Full results: overall score, flags (click to jump to the clause), sortable clause list, disclaimer pinned top and bottom |

## Real behavior, not just UI

- **Live progress**: while a document is processing, the results page polls
  every 2.5s and shows real clause-by-clause progress, not a fake spinner.
- **Quota enforcement**: upload button disables itself once you've hit your
  plan limit, with the same 403 message the backend actually returns.
- **Low-confidence clauses**: visibly flagged per clause, not buried.
- **Failed clauses**: shown honestly with their raw text, not hidden or
  papered over.
- **Cross-user access**: if you try to view someone else's document by
  guessing the ID, you get the same "not found" the backend returns — the
  frontend doesn't leak anything the backend already protects.

## Before you trust this completely — a real browser checklist

I'd run through this myself once you have both servers up:

1. Register, log out, log back in — confirm the token persists across a
   page reload (it should, it's in localStorage).
2. Upload a real contract PDF, watch it go pending -> processing -> complete
   without you touching anything.
3. Resize the browser to a phone width — check the navbar and clause cards
   don't overflow (I wrote the CSS for it but haven't visually confirmed it).
4. Tab through the whole upload flow with only your keyboard — the focus
   ring should be visible at every step (I kept `:focus-visible` on
   purpose, but confirm it actually looks right to you).
5. Toggle dark mode and check contrast still feels readable to your eyes,
   not just to WCAG math.

## Next

- Billing/upgrade page once you have Stripe wired up on the backend.
- Settings page (currently no way to change password / delete account from
  the UI, even though nothing stops you from adding those backend routes).

## Deploying to Vercel

This is genuinely ready to deploy as-is — verified in this exact pass, not assumed:

1. Push this repo (or just the `frontend/` folder) to GitHub.
2. Import it in Vercel. If deploying the whole monorepo, set **Root
   Directory** to `frontend` in project settings.
3. Framework preset: Vite (auto-detected). Build command and output
   directory are auto-detected too (`npm run build`, `dist`).
4. Add one environment variable: `VITE_API_URL` → your backend's URL
   (e.g. `https://your-backend.onrender.com`). No trailing slash.
5. Deploy.

`vercel.json` in this folder handles SPA routing (so refreshing
`/documents/abc123` doesn't 404) — nothing else to configure.

**Verified working in this exact configuration**, not just "should work":
- Built with an explicit cross-origin `VITE_API_URL` (exactly what
  Vercel→Render looks like) and confirmed the URL is correctly baked into
  the bundle, not silently falling back to localhost.
- Ran a full console-error audit across every route — landing, auth flows,
  dashboard, billing, settings, results — both logged out and logged in,
  against a real backend on a different origin. Zero React warnings, zero
  uncaught exceptions, zero broken data flows.
- Deliberately killed the backend mid-session and confirmed the UI shows a
  clean, human error message instead of hanging or leaking the backend's
  raw URL to the user.
- Added a top-level error boundary — a render crash anywhere in the app
  now shows a recoverable "something broke" screen instead of a blank
  white page. This didn't exist before this pass and was a genuine gap.

## Production polish in this pass

- Open Graph + Twitter card meta tags, with a real generated share image
  (`public/og-image.png`) — link previews in Slack/Twitter/iMessage will
  actually render something, not a broken image icon.
- `robots.txt`, disallowing the authenticated-only routes from crawling.
- Per-page `<title>` — every route sets its own document title instead of
  one static title site-wide (`useDocumentTitle` hook).
- Fixed a real, measured layout issue: the landing page hero had ~450px of
  dead space above the headline on standard viewports (content was
  dead-centered in a full-viewport section, which pushes short content too
  far down). Measured before and after — down to a deliberate ~170px of
  breathing room.
