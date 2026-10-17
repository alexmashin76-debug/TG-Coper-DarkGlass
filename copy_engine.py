"""Telegram monitor/copy engine for TG_Coper. Uses a user-authorized Telethon session."""
from __future__ import annotations
import asyncio, re, sqlite3, tempfile, os
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone, time as dt_time, timedelta
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

class CopyEngine:
    def __init__(self, client, state_dir: Path, log: Callable[[str], None] | None = None):
        self.client = client
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / 'tg_coper_history.sqlite3'
        self.log = log or (lambda _: None)
        self._stop = asyncio.Event()
        self._init_db()

    @contextmanager
    def _connect_db(self):
        db = sqlite3.connect(self.db_path)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _init_db(self):
        with self._connect_db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS seen (source TEXT NOT NULL, message_id INTEGER NOT NULL, destination TEXT NOT NULL, status TEXT NOT NULL DEFAULT "copied", created_at TEXT NOT NULL, PRIMARY KEY(source,message_id,destination))')
            db.execute('CREATE TABLE IF NOT EXISTS baselines (source TEXT PRIMARY KEY, message_id INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, kind TEXT NOT NULL, details TEXT NOT NULL)')

    def _event(self, kind, details):
        with self._connect_db() as db:
            db.execute('INSERT INTO events(ts,kind,details) VALUES(?,?,?)', (datetime.now(timezone.utc).isoformat(), kind, str(details)[:1000]))

    def _is_seen(self, source, message_id, destination):
        with self._connect_db() as db:
            return db.execute('SELECT 1 FROM seen WHERE source=? AND message_id=? AND destination=?', (source, message_id, destination)).fetchone() is not None

    def _mark(self, source, message_id, destination, status='copied'):
        with self._connect_db() as db:
            db.execute('INSERT OR REPLACE INTO seen(source,message_id,destination,status,created_at) VALUES(?,?,?,?,?)', (source, message_id, destination, status, datetime.now(timezone.utc).isoformat()))

    @staticmethod
    def _decorate(text, tags='', signature='', remove_links=False):
        text = text or ''
        if remove_links:
            text = re.sub(r'(?i)\b(?:https?://|www\.)\S+', '', text)
            text = re.sub(r'(?i)\bt\.me/\S+', '', text)
            text = re.sub(r'[ \t]{2,}', ' ', text).strip()
        tag_list = []
        for item in re.split(r'[\s,;]+', tags or ''):
            item = item.strip()
            if not item: continue
            item = item if item.startswith('#') else '#'+item
            if re.fullmatch(r'#[\w\u0400-\u04ff]+', item, re.UNICODE) and item.lower() not in {t.lower() for t in tag_list}:
                tag_list.append(item)
        suffix = '\n'.join(x for x in [' '.join(tag_list), (signature or '').strip()] if x)
        if suffix:
            text = (text.rstrip() + '\n\n' + suffix).strip() if text.strip() else suffix
        return text

    @staticmethod
    def _caption_too_long(exc):
        message = str(exc).lower()
        return ('caption is too long' in message or
                ('caption' in message and ('too long' in message or 'length' in message and 'limit' in message)))

    @staticmethod
    def _text_chunks(text, limit=4000):
        """Split long Telegram text conservatively, preferring line boundaries."""
        remaining = (text or '').strip()
        chunks = []
        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break
            cut = remaining.rfind('\n', 0, limit + 1)
            if cut < limit // 2:
                cut = remaining.rfind(' ', 0, limit + 1)
            if cut < limit // 2:
                cut = limit
            chunks.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip()
        return chunks

    async def _send_media_with_caption_fallback(self, destination, path, original_text, tags, signature):
        """Keep the original post; shed added decoration before using a separate text message."""
        tag_list = []
        for item in re.split(r'[\s,;]+', tags or ''):
            item = item.strip()
            if not item:
                continue
            item = item if item.startswith('#') else '#' + item
            if re.fullmatch(r'#[\w\u0400-\u04ff]+', item, re.UNICODE) and item.lower() not in {t.lower() for t in tag_list}:
                tag_list.append(item)

        attempts = []
        # First try the full post, then progressively reduce the tag count.
        for count in range(len(tag_list), -1, -1):
            caption = self._decorate(original_text, ' '.join(tag_list[:count]), signature, False)
            if caption and caption not in attempts:
                attempts.append(caption)
        # If still too long, remove the channel signature, preserving the source text.
        for count in range(len(tag_list), -1, -1):
            caption = self._decorate(original_text, ' '.join(tag_list[:count]), '', False)
            if caption and caption not in attempts:
                attempts.append(caption)

        for caption in attempts:
            try:
                await self.client.send_file(destination, path, caption=caption, parse_mode=None)
                if caption != self._decorate(original_text, tags, signature, False):
                    self.log('Подпись сокращена для лимита Telegram: уменьшено число тегов или убрана подпись канала.')
                return
            except Exception as exc:
                if not self._caption_too_long(exc):
                    raise

        # Even the source text alone is too long for a media caption. Send media
        # without a caption, then preserve all text in regular Telegram messages.
        await self.client.send_file(destination, path, parse_mode=None)
        full_text = self._decorate(original_text, tags, signature, False)
        for chunk in self._text_chunks(full_text):
            await self.client.send_message(destination, chunk, link_preview=False, parse_mode=None)
        self.log('Подпись длиннее лимита Telegram: медиа отправлено отдельно, текст — следующим сообщением.')

    async def _copy_one(self, source, message, destination, destination_key, tags, signature, remove_links):
        if self._is_seen(source, message.id, destination_key): return False
        text = self._decorate(message.message or '', tags, signature, remove_links)
        try:
            # Copy media by downloading then uploading so caption and attribution can be controlled.
            if getattr(message, 'media', None):
                with tempfile.TemporaryDirectory(prefix='tgc_') as tmp:
                    path = await self.client.download_media(message, file=tmp)
                    if path:
                        if text:
                            await self._send_media_with_caption_fallback(
                                destination, path, self._decorate(message.message or '', '', '', remove_links), tags, signature
                            )
                        else:
                            await self.client.send_file(destination, path, parse_mode=None)
                    elif text:
                        await self.client.send_message(destination, text, link_preview=False, parse_mode=None)
                    else:
                        self._mark(source, message.id, destination_key, 'skipped_empty')
                        return False
            elif text:
                await self.client.send_message(destination, text, link_preview=False, parse_mode=None)
            else:
                self._mark(source, message.id, destination_key, 'skipped_empty')
                return False
            self._mark(source, message.id, destination_key)
            self._event('copied', f'{source} #{message.id} -> {destination_key}')
            self.log(f'Скопировано: {source} · публикация {message.id}')
            return True
        except Exception as exc:
            self._event('copy_error', f'{source} #{message.id}: {exc}')
            self.log(f'Ошибка копирования {source} #{message.id}: {str(exc)[:180]}')
            return False

    @staticmethod
    def _keywords(value):
        return [part.strip().casefold() for part in re.split(r"[,;\n]+", value or "") if part.strip()]

    @classmethod
    def _filter_status(cls, text, include_keywords="", exclude_keywords=""):
        body = (text or "").casefold()
        excluded = cls._keywords(exclude_keywords)
        if any(word in body for word in excluded):
            return "excluded"
        included = cls._keywords(include_keywords)
        if included and not any(word in body for word in included):
            return "not_matched"
        return "matched"

    @staticmethod
    def _schedule_state(now, start_time, end_time, timezone_name, daily_limit, copied_today, last_copied_at=None):
        try:
            zone = ZoneInfo(timezone_name or "Europe/Moscow")
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("Europe/Moscow")
        local_now = now.astimezone(zone)
        try:
            start = datetime.strptime(start_time, "%H:%M").time()
            end = datetime.strptime(end_time, "%H:%M").time()
        except (TypeError, ValueError):
            start, end = dt_time(11, 0), dt_time(23, 0)
        if end <= start:
            return False, 0
        start_dt = local_now.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
        end_dt = local_now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
        if not (start_dt <= local_now < end_dt) or copied_today >= max(1, int(daily_limit or 10)):
            return False, 0
        duration = (end_dt - start_dt).total_seconds()
        slot_seconds = duration / max(1, int(daily_limit or 10))
        if copied_today > 0 and last_copied_at:
            try:
                last_utc = datetime.fromisoformat(last_copied_at)
                if last_utc.tzinfo is None: last_utc = last_utc.replace(tzinfo=timezone.utc)
                if (now - last_utc.astimezone(timezone.utc)).total_seconds() < slot_seconds:
                    return False, copied_today
            except (TypeError, ValueError):
                return False, copied_today
        return copied_today < max(1, int(daily_limit or 10)), copied_today + 1

    async def run(self, sources, destination, tags='', signature='', remove_links=False, interval=15, on_count=None, source_enabled=None, on_processed=None, include_keywords='', exclude_keywords='', timezone_name='Europe/Moscow', start_time='11:00', end_time='23:00', daily_limit=10, manual_review=False, on_review=None):
        if not sources: raise ValueError('Добавьте хотя бы один канал-источник.')
        if not destination.strip(): raise ValueError('Укажите канал назначения, например @my_channel.')
        dest = destination.strip()
        dest_entity = await self.client.get_entity(dest)
        me = await self.client.get_me()
        # Ensure we can actually resolve destination and user is logged in before starting.
        if not me: raise RuntimeError('Сессия Telegram не авторизована.')
        baselines = {}
        valid_sources = []
        # Resolve each source independently: one inaccessible channel must not
        # prevent the rest of the user's source list from being monitored.
        for raw in sources:
            source = raw.strip()
            try:
                entity = await self.client.get_entity(source)
                with self._connect_db() as db:
                    row = db.execute('SELECT message_id FROM baselines WHERE source=?', (source,)).fetchone()
                if row is None:
                    latest_id = 0
                    async for msg in self.client.iter_messages(entity, limit=1):
                        latest_id = int(msg.id)
                    baselines[source] = latest_id
                    with self._connect_db() as db:
                        db.execute('INSERT OR IGNORE INTO baselines(source,message_id) VALUES(?,?)', (source, latest_id))
                    self.log(f'Источник подключён; копирование начнётся с новых публикаций: {source}')
                else:
                    baselines[source] = int(row[0])
                    self.log(f'Источник восстановлен из истории: {source}')
                valid_sources.append(source)
            except Exception as exc:
                self._event('error', f'Источник {source}: {exc}')
                self.log(f'Источник пропущен (проверь ссылку/доступ): {source} — {str(exc)[:140]}')
        if not valid_sources:
            raise RuntimeError('Не удалось подключить ни один источник. Проверьте ссылки и доступ аккаунта.')
        sources = valid_sources
        self._stop = asyncio.Event()
        self.log(f'Мониторинг запущен: {len(sources)} источн. • интервал {interval} сек.')
        while not self._stop.is_set():
            copied = 0
            for source in sources:
                if source_enabled is not None and not source_enabled(source):
                    continue
                try:
                    entity = await self.client.get_entity(source)
                    newest = baselines.get(source, 0)
                    pending = []
                    async for msg in self.client.iter_messages(entity, min_id=newest, reverse=True):
                        if msg.id > newest: pending.append(msg)
                    for msg in sorted(pending, key=lambda x: x.id):
                        if on_processed: on_processed(1)
                        if self._is_seen(source, msg.id, dest):
                            newest = max(newest, msg.id)
                            continue
                        filter_status = self._filter_status(getattr(msg, 'message', '') or '', include_keywords, exclude_keywords)
                        if filter_status != 'matched':
                            self._mark(source, msg.id, dest, 'filtered_' + filter_status)
                            self._event('filtered', f'{source} #{msg.id}: {filter_status}')
                            self.log(f'Пропущена публикация {source} #{msg.id}: фильтр ключевых слов ({filter_status})')
                            newest = max(newest, msg.id)
                            continue
                        # Optional human review is invoked only for suspicious promotional/link-heavy text.
                        body_lower = (getattr(msg, 'message', '') or '').casefold()
                        suspicious_markers = ('http://', 'https://', 't.me/', 'подписывайтесь', 'промокод', 'скидка', 'пишите в лс', 'пишите в личные')
                        if manual_review and on_review and any(marker in body_lower for marker in suspicious_markers):
                            approved = await on_review(source, msg)
                            if not approved:
                                self._mark(source, msg.id, dest, 'review_rejected')
                                self._event('review_rejected', f'{source} #{msg.id}: отклонено при ручной проверке')
                                self.log(f'Публикация {source} #{msg.id} отклонена при ручной проверке')
                                newest = max(newest, msg.id)
                                continue
                        # Daily count is calculated in the configured timezone, from successful copies only.
                        try:
                            zone = ZoneInfo(timezone_name or 'Europe/Moscow')
                        except ZoneInfoNotFoundError:
                            zone = ZoneInfo('Europe/Moscow')
                        local_now = datetime.now(timezone.utc).astimezone(zone)
                        local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
                        midnight_utc = local_midnight.astimezone(timezone.utc).isoformat()
                        with self._connect_db() as db:
                            copied_today = db.execute("SELECT COUNT(*) FROM seen WHERE status='copied' AND created_at>=?", (midnight_utc,)).fetchone()[0]
                            latest_row = db.execute("SELECT MAX(created_at) FROM seen WHERE status='copied' AND created_at>=?", (midnight_utc,)).fetchone()
                            last_copied_at = latest_row[0] if latest_row else None
                        allowed, _ = self._schedule_state(datetime.now(timezone.utc), start_time, end_time, timezone_name, daily_limit, copied_today, last_copied_at)
                        if not allowed:
                            # Keep this message at the cursor so it remains queued for the next eligible slot.
                            break
                        was_copied = await self._copy_one(source, msg, dest_entity, dest, tags, signature, remove_links)
                        if was_copied:
                            copied += 1
                            newest = max(newest, msg.id)
                        else:
                            # Do not advance the cursor past a failed post; retry it on the next pass.
                            break
                    if newest > baselines.get(source, 0):
                        baselines[source] = newest
                        with self._connect_db() as db:
                            db.execute('INSERT OR REPLACE INTO baselines(source,message_id) VALUES(?,?)', (source, newest))
                except Exception as exc:
                    details = str(exc)
                    self._event('error', f'Источник {source}: {details}')
                    if 'wrong session id' in details.lower() or 'security error while unpacking' in details.lower():
                        self.log('Telegram вернул неверный session ID. Переподключаюсь; проверь, что другая копия TG_Coper не использует этот же файл сессии.')
                        try:
                            if self.client.is_connected():
                                await self.client.disconnect()
                            await asyncio.sleep(1.0)
                            await self.client.connect()
                            me = await self.client.get_me()
                            if not me:
                                raise RuntimeError('Сессия больше не авторизована')
                            self.log('Соединение Telegram восстановлено; мониторинг продолжится.')
                        except Exception as reconnect_exc:
                            self.log('Не удалось восстановить Telegram-соединение: ' + str(reconnect_exc)[:160])
                            raise RuntimeError('Telegram-сессия не работает. Закрой другие копии программы, проверь сеть и повторно подключи сессию. Детали: ' + str(reconnect_exc)[:120]) from reconnect_exc
                    else:
                        self.log(f'Ошибка источника {source}: {details[:180]}')
                await asyncio.sleep(0.25)
            if on_count: on_count(copied)
            try: await asyncio.wait_for(self._stop.wait(), timeout=max(5, int(interval)))
            except asyncio.TimeoutError: pass
        self.log('Мониторинг остановлен.')

    def stop(self):
        self._stop.set()

    def stats(self):
        with self._connect_db() as db:
            copied = db.execute("SELECT COUNT(*) FROM seen WHERE status='copied'").fetchone()[0]
            errors = db.execute("SELECT COUNT(*) FROM events WHERE kind IN ('error','copy_error')").fetchone()[0]
            copy_errors = db.execute("SELECT COUNT(*) FROM events WHERE kind='copy_error' OR (kind='error' AND details NOT LIKE 'Источник %')").fetchone()[0]
            events = db.execute('SELECT ts,kind,details FROM events ORDER BY id DESC LIMIT 100').fetchall()
        return {'copied': copied, 'errors': errors, 'copy_errors': copy_errors, 'events': events}
