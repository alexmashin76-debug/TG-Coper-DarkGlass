# TG_Coper v36 — Dashboard refresh

- Home screen now follows the requested dashboard structure: four KPI cards, views-history graph area, recent events, and a prominent monitoring/control strip.
- Added an actual source-count card; KPI values use local app counters and saved stats only, with no invented Telegram metrics.
- Source management remains in the dedicated Sources section; settings, filters, journal, statistics and authorization navigation are preserved.
- Moved the Statistics page actions into the header so they no longer overlap the metric row.
- Kept the existing Dark Glass wallpaper, transparent panels, neon outlines, and vector icon style.
- Validation: 16 automated tests pass. Screenshots were captured from a running Tkinter GUI under Xvfb; Telegram is not connected in the screenshots, so real account statistics are empty.
