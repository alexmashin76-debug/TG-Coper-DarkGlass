# TG_Coper v40 — Sources & Live Monitoring

- Source entry accepts public Telegram usernames and links, including `https://t.me/s/channel_name/123` preview URLs.
- Source section now shows enabled/disabled state and allows removing a source while monitoring is stopped.
- Source addition/removal is blocked while monitoring is running to avoid changing the monitored list mid-cycle.
- Main-screen source switches are live: enabling/disabling a source changes whether new posts from it are processed without restarting the monitor.
- Monitoring startup validates sources independently; one unavailable source no longer prevents valid sources from being monitored. If all sources fail to resolve, a clear error is returned.
- Existing copy engine keeps duplicate protection, media copying, optional link removal, tags, signature and persisted message baselines.
- Tested with 20 automated tests. Real Telegram copy still requires user authorization, valid source channels, and posting rights in the destination.

## v41 — Search fix
- Made the top search field interactive: click it and type to filter results.
- Search filters source names in the Sources section and event time/level/message in the Journal section.
- Backspace edits the query; Enter/Escape exits search typing mode; clear the query by backspacing.
- Journal now shows recent network log entries with time, level and message, and reports the number of matching events.
- Validated syntax and ran the automated suite (20 tests).
