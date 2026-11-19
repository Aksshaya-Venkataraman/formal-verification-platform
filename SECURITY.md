# Security

## Reporting a vulnerability

Use GitHub's private vulnerability reporting (Security → Report a vulnerability).

## Running untrusted logic problems

Users submit text that ends up as input to native programs, so this is the main attack surface.

- **Input never reaches a prover verbatim.** A strict parser accepts only the TPTP FOF/CNF subset
  and rejects `include`, quoted names, unknown `$` symbols and anything unexpected. Each prover gets
  text re-serialised from the syntax tree.
- **No shell.** Provers are started with fixed argument lists (`subprocess`, `shell=False`) and
  fixed binary paths resolved at start-up.
- **Sandbox per run.** Private temp directory, minimal environment, `prlimit` limits on CPU time,
  address space (3 GB), output file size (5 MB), open files, no core dumps; wall-clock timeout that
  kills the whole process group; at most `MAX_CONCURRENT_PROVERS` processes server-wide.
- **Container.** Non-root user, read-only root filesystem with a size-limited `/tmp`, all Linux
  capabilities dropped, `no-new-privileges`.
- **Output** is truncated, stored as text and rendered by React as text (never HTML).

## Web application controls

| Concern | Control |
|---|---|
| Sessions | HttpOnly, Secure, SameSite=Strict `__Host-` cookie; regenerated at login; `session_version` lets password changes and "log out everywhere" revoke old cookies |
| CSRF | Per-session token required in `X-CSRF-Token` on every state-changing request, plus an Origin allow-list |
| Passwords | Argon2id, minimum 12 characters, constant-time path for unknown emails, generic error messages |
| Authorisation | Runs and problems are always queried with the owner's ID, so other users get 404; admin endpoint requires `is_admin` |
| Validation | Strict schemas (`extra="forbid"`), allow-listed prover names, time limit capped, 64 KB problem / 256 KB request limits, `<`/`>` rejected in titles |
| Abuse | Rate limits on login, registration and verification, shared through Redis |
| Headers | CSP (`script-src 'self'`, no inline script, `frame-ancestors 'none'`), HSTS, `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `no-store` on API responses |
| Hosts / proxy | Trusted-host list; proxy headers trusted only from the single Caddy hop |
| Production mode | Debug off, generic 500 responses, JSON logs without request bodies |
| Secrets | Environment only; `.env` git-ignored and created with mode 600; weak `SECRET_KEY` refused; gitleaks in CI |
| Database | Non-superuser role owning only its database; not exposed outside the internal network |
| Supply chain | Hash-locked Python dependencies, `npm ci` from a lock file, pip-audit/npm audit/Bandit in CI, Dependabot, Otter tarball SHA-256 verified, Vampire commit pinned |
