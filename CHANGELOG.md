# Changelog

## v0.1.0 — 2026-11-06

First release. The shape is fixed; the catalogue is a file.

### The loop
- `config/services.yaml` → `tools/build.py` → `site/services.json` → a static page.
- The page has no write path: no forms, no sessions, no admin panel, no database.
- The build refuses a broken catalogue with an error that names the category and the service.

### The catalogue
- Categories, services, descriptions, tags, status labels.
- Pinned row across categories.
- Dark and light themes (`theme:`).
- Per-category accent colours.
- Icon chain: declared icon → host favicon → monogram.

### Truth about status
- `tools/probe.py` checks every service over a real socket and writes `site/status.json`.
- The page renders a live dot from that file. The browser never pings anything, because a
  cross-origin fetch without CORS on the target tells you nothing.

### Deployment
- Multi-stage Docker image; the config is validated **during the build**, so a broken catalogue
  cannot be shipped.
- Container runs read-only, non-root, `cap_drop: ALL`, `no-new-privileges`, with a CSP and a
  healthcheck.
- `./site` is mounted read-only, so a host-side rebuild updates the page with no restart.

### Quality
- 11 tests on the validator, which is the product.
- CI: tests, `--check`, build, and a guard that fails the run if `index.html` grows an inline script.

### Known limits
- Icons are external URLs; with no internet a tile falls back to its monogram.
- The probe is HTTP-level. It says the server answered, not that the application is healthy.
- No users, no roles, no write API — by design, not by omission.
