# Support Engineer — landing site

A one-page presentation site for the Support Engineer agent, built with **React +
Vite**. Light, professional theme with an agent "reasoning graph" background
(self-contained SVG — no image assets, no 3D, no external requests).

## Develop

```bash
cd web
npm install
npm run dev        # http://localhost:5173
```

## Build / preview

```bash
npm run build      # outputs to web/dist
npm run preview    # serves the production build at /Support-Engineer/
```

## Structure

- `index.html` — the landing.
- `maintenance.html` / `unpublish.html` — frozen state screens reused by the
  workflows (they set `data-state` on `#root`; see `src/StateScreen.jsx`).
- `src/ui/Background.jsx` — the deterministic agent-graph background.
- `src/sections/*` — Hero, About, Flow, Stack, Pipeline, Cta, Footer.

The site is served from a GitHub Pages **project** URL
(`https://<user>.github.io/Support-Engineer/`), so `vite.config.js` sets
`base` to `/Support-Engineer/` in production. **If you rename the repo, update
`REPO_NAME` in `vite.config.js`.**

## Publishing (GitHub Pages)

Two workflows in `.github/workflows/`:

- **`deploy-pages.yml`** — *Publish landing to GitHub Pages*. Runs on push to
  `master` (when `web/**` changes) and via **Actions → Run workflow**. On the
  first run it auto-enables Pages with *Source: GitHub Actions*.
- **`unpublish-pages.yml`** — *Unpublish landing*. Manual only; type `OFFLINE`
  to confirm. Replaces the live site with the "Page unpublished" screen. To fully
  disable Pages, set **Settings → Pages → Source** to *None*.

No secrets are required — both workflows use the built-in `GITHUB_TOKEN` with
`pages: write` / `id-token: write` permissions.
