# TG_Coper — Dark Glass, functional build

Standalone Telegram channel monitor and publication copier. The interface keeps the neon crystal background and transparent outline panels; Telegram actions are connected to Telethon rather than simulated.

## Main workflow
1. On Kali/Linux, open a terminal in the extracted project folder and run `./start_gui.sh`. The launcher checks Python 3, Tkinter, Pillow and Telethon; on Kali/Debian it attempts to install missing system components with `apt-get` and may request the system password through `sudo`. If Python libraries are missing, it prepares `.venv` and installs requirements there. No manual venv activation or pip command is required. Startup output is saved to `startup_error.log`; if launch fails, send that log. For the first diagnostic run, launch from a terminal so any password prompt is visible. On Windows use `install_requirements.bat` and `start_gui.bat`.
4. Click **Авторизация**. Enter your Telegram API ID and API HASH from `my.telegram.org`, then click **Проверить связь**. The app performs a real Telegram API request; it will not enable code-request until Telegram replies. If that passes, enter your phone and request the code. If Telegram asks for 2FA, enter that password too.
5. Add public source channels as `@username` or `https://t.me/username`.
6. Open **Настройки**. Set the destination channel, tags, signature, polling interval, include/exclude keywords, timezone, copy window and daily limit. The account must have permission to publish in the destination channel.
7. Click **Запустить**. TG_Coper establishes a baseline for new sources and then polls for new posts. It does not backfill the entire source history on first start.

## Implemented
- Telegram user login via Telethon, including 2FA and session restoration on next launch.
- Explicit Telegram connectivity check via a real API round-trip before enabling code request; login re-checks the live connection before sending sign-in data. Network/API errors are shown in the dialog rather than silently continuing.
- Persistent source list and settings.
- Source access checks.
- Polling of source channels and copying newly published text/media to the destination.
- Optional URL removal, automatic hashtags and channel signature.
- Text-only include/exclude keyword filters (source community names are not considered).
- Configurable timezone, daily copy window, max posts per day and spacing between successful copies.
- A local session lock to prevent two TG_Coper processes from using the same Telethon session at once, plus reconnect attempts after Telegram wrong-session-ID errors.
- SQLite history and duplicate prevention across restarts.
- Persistent copy/error counts and activity log.
- Retry behavior: failed publications do not advance the source cursor past the failed post.
- Local tests for formatting, media-copy path, duplicate prevention, source validation, UI controls and startup-state handling.

## Tests run for this build
Run `python -m unittest -v` from this folder. GUI tests require a desktop session on Windows; in Linux they can be run under Xvfb. The included local suite uses fake Telegram client objects and does not publish real messages.

## Important limits / security
- Real Telegram connectivity could not be confirmed from the build environment: outbound DNS/network access is unavailable here and Telethon is not installed in the isolated runner. The connection-check path is implemented, but you must run it on Kali with internet/VPN/Tor available before entering the code. Complete the first login and verify with a private test channel before relying on it.
- On first start for a source, current history is treated as the baseline; only later posts are copied. Up to 30 posts per source per polling cycle are no longer a limit; the engine fetches messages newer than its cursor.
- Album grouping, polls, stories, protected-content copying, and exact preservation of original formatting/entities are not implemented. Media posts are downloaded and re-uploaded with the decorated caption.
- The Telegram API HASH is saved in `tg_coper_state.json` in plain text for convenience. Keep that file and `telegram_user_session.session` private; never send them to anyone. Remove the state file before sharing the project archive.
- Telegram rate limits apply. Keep the interval conservative and only monitor channels you are allowed to access.

## Статистика каналов (низкая нагрузка)
В разделе «Статистика» показываются снимки статистики Telegram: число подписчиков канала назначения, сумма просмотров последних 10 публикаций, количество доступных проверенных каналов и история замеров (до 48 точек). Сбор запускается в фоновом потоке asyncio и повторяется раз в 30 минут; график рисуется средствами Tkinter Canvas, поэтому GPU-ускорение не требуется. Можно запросить ручное обновление кнопкой «Обновить сейчас». Для числа подписчиков и просмотров нужен доступ к каналу назначения через подключённый Telegram-аккаунт. Это не статистика уникальных посетителей: Telegram API не предоставляет такой показатель обычным пользовательским запросом.


### Запуск и зависимости в Kali/Linux

`start_gui.sh` writes a fresh `startup_error.log` on each launch and prints progress live. It attempts to install Python 3 if absent, then Tkinter, then prepares `.venv` and installs missing Pillow/Telethon dependencies when needed. Existing system libraries are reused where possible. System package installation requires Kali/Debian `apt-get` and may ask for the OS password through `sudo`. Launch from a terminal for the first run; if it fails, send the complete `startup_error.log`. This environment cannot verify apt installation or launch a real desktop on the user’s Kali VM.

### Проверка связи и возврат из статистики

Кнопка «Проверить связь» делает независимый HTTPS-запрос к официальному сайту `https://telegram.org/` и не требует API ID/API HASH. Она подтверждает доступность сайта, но не подтверждает доступность Telegram API или успешность авторизации. Для запроса кода по-прежнему нужны собственные API ID, API HASH и номер телефона. На экране статистики есть кнопка «На главную».

## Изменения версии v30
- Переработан Linux-стартер: он теперь пытается установить Python 3, если тот отсутствует, затем проверяет Tkinter и Python-зависимости.
- Запуск всегда пишет подробный вывод в `startup_error.log`, включая ошибки импорта и traceback приложения; при запуске из терминала оставляет сообщение об ошибке на экране.
- Проверены синтаксис Bash и компиляция Python. В текущей изолированной среде тесты движка/сетевой проверки проходят, но GUI-тестам нужен доступный X display/Xvfb. Реальный вход в Telegram, публикация и установка пакетов в Kali VM здесь не выполнялись.

### Финальные исправления v46
- Счётчик на главном экране показывает активные источники / общее число источников.
- Источник можно удалить из списка во время мониторинга; он сразу отключается для текущего цикла.
- Длинные списки источников и журнал прокручиваются колесом мыши и вертикальной полосой прокрутки.
- Журнал целиком сохраняется в `logs/journal_001.jsonl`, `journal_002.jsonl` и далее — по 100 записей в файл. В оперативной памяти остаются последние 100, а раздел журнала читает полную историю с диска.
- Счётчик ошибок статуса отражает ошибки копирования/публикации, а ошибки проверки соединения и источников остаются в журнале.
- Сброс счётчиков не удаляет базу истории публикаций и защиту от дублей.
