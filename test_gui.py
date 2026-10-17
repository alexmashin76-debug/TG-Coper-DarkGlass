import tempfile, tkinter as tk, unittest
from pathlib import Path
import tg_coper_panel
from tg_coper_panel import App

class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=tk.Tk(); cls.root.withdraw()
        cls.tmp=tempfile.TemporaryDirectory()
        tg_coper_panel.STATE_FILE=Path(cls.tmp.name)/'state.json'
        tg_coper_panel.LOG_DIR=Path(cls.tmp.name)/'logs'
        cls.app=App(cls.root); cls.root.update_idletasks()
    @classmethod
    def tearDownClass(cls):
        try: cls.root.destroy()
        finally: cls.tmp.cleanup()
    def test_add_source(self):
        self.app.sources=[]; self.app.entry='@test_channel'; self.app.add_source()
        self.assertIn('@test_channel', self.app.sources)
    def test_start_without_destination_does_not_fake_running(self):
        self.app.sources=['@test_channel']; self.app.destination=''; self.app.start()
        self.assertFalse(self.app.running)
        self.assertIn('назначения',self.app.lastlog)
    def test_reject_invalid_source(self):
        self.app.sources=[]; self.app.entry='not a channel'; self.app.add_source()
        self.assertNotIn('not a channel', self.app.sources)
    def test_normalize_source(self):
        self.app.sources=[]; self.app.entry='https://t.me/example_channel'; self.app.add_source()
        self.assertIn('@example_channel', self.app.sources)

    def test_normalize_public_preview_link(self):
        self.app.sources=[]; self.app.entry='https://t.me/s/example_channel/123'; self.app.add_source()
        self.assertIn('@example_channel', self.app.sources)

    def test_remove_source_when_stopped(self):
        self.app.running=False; self.app.sources=['@remove_me']; self.app.source_enabled={'@remove_me':True}
        self.app.remove_source('@remove_me')
        self.assertNotIn('@remove_me', self.app.sources)
        self.assertNotIn('@remove_me', self.app.source_enabled)

    def test_remove_source_while_monitoring_disables_then_removes_from_ui(self):
        self.app.running=True; self.app.sources=['@keep_me']; self.app.source_enabled={'@keep_me': True}
        self.app.remove_source('@keep_me')
        self.assertNotIn('@keep_me', self.app.sources)
        self.assertFalse(self.app.source_enabled['@keep_me'])
        self.app.running=False
    def test_global_search_matches_journal_text_case_insensitively(self):
        self.app.search_query='ERROR'
        self.assertTrue(self.app._matches_search('Ошибка ERROR подключения'))
        self.assertFalse(self.app._matches_search('Успешно опубликовано'))
        self.app.search_query=''
        self.assertTrue(self.app._matches_search('любое событие'))

    def test_journal_is_persisted_and_rotated_after_100_events(self):
        for i in range(105): self.app._network_event('INFO', f'journal-test-{i}')
        files=list(tg_coper_panel.LOG_DIR.glob('journal_*.jsonl'))
        self.assertGreaterEqual(len(files), 2)
        self.assertLessEqual(len(self.app.network_log), 100)
        all_rows=self.app._read_all_journal()
        self.assertTrue(any('journal-test-104' in row['message'] for row in all_rows))

    def test_toggle_setting(self):
        before=self.app.flags[0]; self.app.toggle(0)
        self.assertEqual(self.app.flags[0], not before)
    def test_auth_window_opens(self):
        self.app.open_auth(); self.root.update_idletasks()
        self.assertTrue(self.app.auth_window.winfo_exists()); self.app.auth_window.destroy()

    def test_navigation_keeps_direct_sidebar_sections(self):
        for section in ('Главная','Источники','Настройки','Фильтры','Журнал','Статистика','О программе'):
            self.app.nav(section)
            self.root.update_idletasks()
            self.assertEqual(self.app.active, section)
            self.assertTrue(self.app.canvas.winfo_exists())

    def test_navigation_does_not_change_monitoring_flag(self):
        self.app.running=True
        self.app.nav('Статистика')
        self.root.update_idletasks()
        self.assertTrue(self.app.running)
        self.app.running=False

    def test_code_request_is_blocked_until_connection_check(self):
        self.app.open_auth(); self.root.update_idletasks()
        self.app.auth_request_code()
        self.assertIn('Проверить связь', self.app.auth_status.get())
        self.assertEqual(str(self.app.auth_login_btn['state']), 'disabled')
        self.app.auth_window.destroy()

if __name__=='__main__': unittest.main()
