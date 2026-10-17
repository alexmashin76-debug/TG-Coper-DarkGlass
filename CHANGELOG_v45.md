# TG_Coper v45 — Caption limit fallback

- When Telegram rejects a media caption as too long, retry the same post with fewer appended tags first.
- If needed, remove the channel signature while preserving the source post text.
- If the source text itself exceeds Telegram's media-caption limit, publish the media without a caption and send the full decorated text as one or more follow-up messages.
- Added engine tests for tag reduction and long-source-caption fallback.
- Numeric view graph and v44 interface are retained.
