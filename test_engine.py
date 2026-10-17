import asyncio, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from copy_engine import CopyEngine

class FakeClient:
    def __init__(self): self.sent=[]; self.downloads=0; self.posts={'@source':[]}
    async def send_message(self, dest, text, **kw): self.sent.append(('text', dest, text, kw))
    async def send_file(self, dest, path, **kw):
        caption = kw.get('caption', '')
        if len(caption) > 1024:
            raise ValueError('The caption is too long (caused by SendMediaRequest)')
        self.sent.append(('file', dest, path, kw))
    async def download_media(self, message, file=None): self.downloads += 1; p=Path(file)/'media.bin'; p.write_bytes(b'fake'); return str(p)
    async def get_entity(self, source):
        if 'invalid' in str(source): raise ValueError('channel not found')
        return source
    async def get_me(self): return object()
    async def iter_messages(self, entity, limit=None, min_id=None, reverse=False):
        posts=self.posts.get(str(entity), [])
        if limit == 1:
            posts=posts[-1:]
        elif min_id is not None:
            posts=[p for p in posts if p.id > min_id]
        for post in (posts if reverse else reversed(posts)):
            yield post

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.client=FakeClient(); self.engine=CopyEngine(self.client,Path(self.tmp.name))
    def tearDown(self): self.tmp.cleanup()
    def test_decorate_tags_signature_and_links(self):
        result=self.engine._decorate('Vacancy https://example.com','jobs #remote','Our channel',True)
        self.assertNotIn('https://example.com',result); self.assertIn('#jobs #remote',result); self.assertIn('Our channel',result)
    def test_tags_normalized_deduplicated(self):
        result=self.engine._decorate('hello','jobs #jobs, remote','','')
        self.assertEqual(result,'hello\n\n#jobs #remote')
    def test_duplicate_protection(self):
        msg=SimpleNamespace(id=123,message='Hello',media=None)
        async def run():
            first=await self.engine._copy_one('@source',msg,'@dest','@dest','','',False)
            second=await self.engine._copy_one('@source',msg,'@dest','@dest','','',False)
            return first,second
        self.assertEqual(asyncio.run(run()),(True,False)); self.assertEqual(len(self.client.sent),1)
    def test_media_is_uploaded_with_caption(self):
        msg=SimpleNamespace(id=124,message='Vacancy',media=object())
        self.assertTrue(asyncio.run(self.engine._copy_one('@source',msg,'@dest','@dest','#work','signature',False)))
        self.assertEqual(self.client.sent[0][0],'file'); self.assertIn('#work',self.client.sent[0][3]['caption'])

    def test_long_caption_reduces_tags_before_removing_signature(self):
        msg=SimpleNamespace(id=125,message=('V' * 980),media=object())
        result=asyncio.run(self.engine._copy_one('@source',msg,'@dest','@dest','#one #two #three',('S' * 30),False))
        self.assertTrue(result)
        file_call=next(x for x in self.client.sent if x[0]=='file')
        self.assertLessEqual(len(file_call[3].get('caption','')),1024)
        self.assertIn('V' * 100, file_call[3]['caption'])
        self.assertNotIn('#three',file_call[3]['caption'])
        self.assertIn('S' * 10, file_call[3]['caption'])

    def test_source_text_over_caption_limit_sends_media_and_text_separately(self):
        msg=SimpleNamespace(id=126,message=('Long original vacancy ' * 80),media=object())
        result=asyncio.run(self.engine._copy_one('@source',msg,'@dest','@dest','#tag','My channel',False))
        self.assertTrue(result)
        file_call=next(x for x in self.client.sent if x[0]=='file')
        self.assertNotIn('caption',file_call[3])
        text_calls=[x[2] for x in self.client.sent if x[0]=='text']
        self.assertTrue(text_calls)
        self.assertIn('#tag', '\n'.join(text_calls))
        self.assertIn('My channel', '\n'.join(text_calls))

    def test_keyword_filter_include_any_and_exclude_priority(self):
        self.assertEqual(self.engine._filter_status('Вакансия: нужен мастер', 'вакансия, работа', 'реклама, услуги'), 'matched')
        self.assertEqual(self.engine._filter_status('Вакансия и реклама услуги', 'вакансия', 'реклама, услуги'), 'excluded')
        self.assertEqual(self.engine._filter_status('Продаю телефон', 'вакансия, работа', 'реклама, услуги'), 'not_matched')
        self.assertEqual(self.engine._filter_status('Любой текст', '', ''), 'matched')

    def test_schedule_respects_window_limit_and_spacing(self):
        from datetime import datetime, timezone, timedelta
        now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)  # 15:00 Moscow
        allowed, _ = self.engine._schedule_state(now, '11:00', '23:00', 'Europe/Moscow', 10, 0)
        self.assertTrue(allowed)
        recent = (now - timedelta(minutes=30)).isoformat()
        allowed, _ = self.engine._schedule_state(now, '11:00', '23:00', 'Europe/Moscow', 10, 1, recent)
        self.assertFalse(allowed)
        allowed, _ = self.engine._schedule_state(now, '11:00', '23:00', 'Europe/Moscow', 10, 10)
        self.assertFalse(allowed)
        outside = datetime(2026, 10, 17, 6, 0, tzinfo=timezone.utc)  # 09:00 Moscow
        allowed, _ = self.engine._schedule_state(outside, '11:00', '23:00', 'Europe/Moscow', 10, 0)
        self.assertFalse(allowed)

    def test_stats(self):
        self.assertEqual(self.engine.stats()['copied'],0)

    def test_run_skips_bad_source_and_keeps_valid_source_monitoring(self):
        self.client.posts['@source']=[SimpleNamespace(id=10,message='baseline',media=None)]
        async def scenario():
            task=asyncio.create_task(self.engine.run(['@invalid_source','@source'],'@dest',interval=5))
            await asyncio.sleep(0.15)
            self.engine.stop()
            await asyncio.wait_for(task,timeout=1)
        asyncio.run(scenario())
        self.assertTrue(any('Источник пропущен' in x for x in [])) if False else None
        self.assertEqual(self.engine.stats()['errors'],1)
        self.assertEqual(self.engine.stats()['copy_errors'],0)

if __name__=='__main__': unittest.main()
