# TG_Coper v44 — Numeric view graph

- Added numeric Y-axis tick labels to the main dashboard views chart.
- Added the exact latest measured views value above the latest graph point.
- Added numeric Y-axis tick labels and latest measured value to the dedicated Statistics screen.
- Added grid lines aligned to numeric ticks for easier reading.
- The graph continues to use collected Telegram statistics only; no synthetic values are inserted by the application.

## Verification
- Python syntax compilation passed.
- Engine tests: 6 passed.
- GUI tests under Xvfb: 13 passed.
- Live Telegram publication/real-account collection was not tested in this environment.
