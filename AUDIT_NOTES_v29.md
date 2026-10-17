TG_Coper v29 — audit notes

Changes:
- Corrected stale UI wording about test mode and copying not being connected.
- Clarified that the pre-auth connectivity check reaches telegram.org only; API connectivity is verified separately during sign-in.
- Tightened POSIX permissions on state/session files to 0600.
- Avoided displaying a false zero for unavailable subscriber counts.
- Added .venv to .gitignore.

Validation:
- python -m compileall -q . — passed.
- xvfb-run -a python -m unittest -v — 14 tests passed.
- No live Telegram login or real channel publication was attempted from the isolated test environment. Validate with a private test channel before relying on unattended operation.
