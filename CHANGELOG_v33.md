TG_Coper DarkGlass v33 — persistent navigation and real statistics view

Changes:
- Statistics now renders inside the shared workspace instead of replacing the entire window. The sidebar remains available, so the user can move directly between sections without returning to Home.
- Statistics cards, history, and graph use collected/persisted Telegram snapshots; when no snapshots exist, the UI explicitly says data is not available rather than inventing values.
- Navigation is presentation-only and does not stop the asynchronous monitoring task. The Telegram client runs work on its own asyncio loop/thread.
- Added GUI regression tests for direct navigation and preservation of the monitoring state during navigation.

Validation performed in the build environment:
- Python compilation: passed.
- Engine and network-check tests: passed.
- GUI tests under Xvfb virtual display: passed.
- Total automated tests: 16 passed.

Not verified here: live Telegram login, live channel permissions, and end-to-end copying against the user's Telegram account. Those require the user's account/network and must be checked on their machine.
