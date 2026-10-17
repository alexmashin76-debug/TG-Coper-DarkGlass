# TG_Coper v46 — final stability pass

- Dashboard source counter now shows enabled sources versus total sources, so disabling a source updates the active count immediately.
- Removing a source works while monitoring is active: it is removed from the visible/configured list and disabled for the running monitor loop.
- Quick action “Новый источник” now opens the Sources page and focuses the entry field.
- Added vertical scrolling for long Sources and Journal views, including mouse wheel support.
- Journal now persists all events to `logs/journal_001.jsonl`, `journal_002.jsonl`, etc.; each file contains up to 100 records. The UI keeps only the latest 100 records in memory but can display/search the complete disk history.
- Status “Ошибки” now counts copy/publication errors only; general source/connectivity failures remain visible in the Journal.
- “Проверить ссылки” no longer overwrites the copy-error counter with general source-check failures.
- “Сбросить результаты” now confirms the action and resets displayed counters without deleting publication history or duplicate protection.
- View-stat history retention increased to 10,000 snapshots so longer selected ranges are not discarded after 48 samples.
- Added tests for journal rotation and source removal during monitoring.

## Подготовка v47 — расписание, фильтры и устойчивость сессии
- Добавлены фильтры по ключевым словам в тексте поста. Имя/название исходного канала не участвует в фильтрации; исключающие слова имеют приоритет.
- Добавлены часовой пояс IANA, окно копирования, дневной лимит и интервал между публикациями. По умолчанию: Europe/Moscow, 11:00–23:00, до 10 публикаций в день.
- Посты, не прошедшие фильтр, помечаются в локальной истории и не повторно обрабатываются.
- Добавлена блокировка локального файла сессии от одновременного использования несколькими копиями TG_Coper.
- При Telegram-ошибке `wrong session ID` мониторинг пытается переподключиться и пишет понятное диагностическое сообщение.
- Добавлены тесты фильтров и расписания.
