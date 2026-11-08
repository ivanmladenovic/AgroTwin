# AgroTwin Marketing Website

One-page marketing site for AgroTwin (`Website/`), separate from the product SPA in `SOFTWARE/frontend`.

## Stack

- Vite + React 19 + TypeScript
- Tailwind CSS v4
- Lucide icons
- Brand tokens aligned with the AgroTwin application

## Scripts

```bash
npm install
npm run dev      # http://localhost:5175
npm run build
npm run lint
npm run preview
```

## Languages

- Default: Serbian (Latin) — `sr`
- Secondary: English — `en`
- Persistence: `localStorage` key `agrotwin.locale` (same as the AgroTwin app)

## Environment

Copy `.env.example` to `.env`:

| Variable | Purpose |
|----------|---------|
| `VITE_APP_URL` | AgroTwin app origin. Individual CTAs link to `{VITE_APP_URL}/login` (no public registration in the current product). |
| `VITE_SITE_URL` | Marketing origin (`https://myagrotwin.com`). Canonical, Open Graph, sitemap. |
| `VITE_CONTACT_EMAIL` | Footer + mailto fallback (`contact@myagrotwin.com`). |
| `VITE_ENTERPRISE_CONTACT_URL` | Optional POST endpoint for enterprise inquiries. When unset, validated submissions open a mailto draft and **do not** claim server-side success. |

## Production domain

- Marketing site: **https://myagrotwin.com**
- `public/robots.txt` → sitemap at `/sitemap.xml`
- App login CTAs point to `https://app.myagrotwin.com/login` by default (`VITE_APP_URL`).

## Notes

- Does not modify `SOFTWARE/` application or backend logic.
- Product mockups are illustrative UI composites inspired by the real app; the orchard hero photo is a real AgroTwin marketing asset.
- No invented usage limits, testimonials, customer logos or statistics.
