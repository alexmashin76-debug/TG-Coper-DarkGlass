# TG_Coper v47 — schedule, filters and session stability

- Added include/exclude keyword filters against the post text only; source community names are not considered. Exclusion terms take priority.
- Added configurable IANA timezone, copy window, daily post limit, and minimum spacing between successful copies. Defaults: `Europe/Moscow`, 11:00–23:00, 10 posts/day.
- Posts rejected by keyword filters are recorded locally and not retried on every polling cycle.
- Added optional manual review for link-heavy/promotional-looking posts. Off by default; when enabled, the user can approve or reject candidates in a dialog.
- Added an OS-level lock around the local Telethon session so a second TG_Coper process cannot use the same session simultaneously.
- Added reconnect handling for Telegram's `wrong session ID` protocol errors with clear diagnostics.
- Tests: 26 tests passed under Xvfb. Real Telegram login/copying was not run in this environment.
