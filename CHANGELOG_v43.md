# TG_Coper v43 — processed counter and configurable views graph

- Fixed the main-screen `Обработано` counter: it now increments for each new source post actually examined during a monitoring cycle, independently from the publication count.
- Added main-screen views graph period controls: 3 hours, 24 hours, 7 days, 30 days, and all available history.
- Selected graph period is saved in local state and restored on next launch.
- New statistics samples include an ISO timestamp so period filtering uses actual dates/times. Older samples without timestamps remain visible as legacy history.
- Monitoring remains asynchronous and continues while navigating between sections.

## Verification
- `python -m py_compile tg_coper_panel.py copy_engine.py` — passed.
- `xvfb-run -a python -m unittest -v` — 21 tests passed.
- Main-screen screenshots captured under Xvfb. Real Telegram connection/publication was not performed in the isolated build environment.
