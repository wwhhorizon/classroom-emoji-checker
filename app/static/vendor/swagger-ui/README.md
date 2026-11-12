# Local Swagger UI distribution

The vendored `swagger-ui-bundle.js` and `swagger-ui.css` are unmodified files from
the official `swagger-api/swagger-ui` release **v5.34.1**. The upstream Apache 2.0
license and NOTICE are included. `SOURCE.json` records the precise source URLs,
file sizes and SHA-256 checksums.

Upstream release: https://github.com/swagger-api/swagger-ui/releases/tag/v5.34.1

`index.html`, `initializer.js` and `docs.css` are project integration files. The
documentation loads only local assets and `/openapi.json`; remote validation and
query-supplied configuration are disabled. Its initializer is an external local
script, so the application retains `script-src 'self'` without inline-script or
CDN exceptions. Bearer authorization entered into Swagger is held in memory for
the current page only; application session cookies retain the backend's normal
expiration and revocation rules.
