TG_Coper DarkGlass v32 — readability and navigation

Changes:
- Darkened the neon wallpaper slightly to improve text contrast without removing the visual background.
- Reworked cards and buttons as dark-tinted glass surfaces that still show the wallpaper beneath them.
- Added working section views for Sources, Filters, Journal, Settings summary, and About.
- Added an explicit “На главную” button to every section, including Statistics.
- Closing the Settings dialog now returns the app to the main screen; saving settings also returns to the main screen.
- The Sources section includes a channel input, Add, and Check actions.
- The Filters section exposes the existing publication-processing toggles without changing their behavior.

Validation:
- Python syntax check passed.
- GUI tests: 7 passed.
- Engine tests: 5 passed.
- Navigation render check passed for all sections.
