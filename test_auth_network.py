import asyncio
import io
import unittest
from unittest.mock import patch
from tg_coper_panel import TelegramAuthManager

class FakeResponse:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n=-1): return b'<html>Telegram</html>'[:n]

class NetworkCheckTests(unittest.TestCase):
    def test_website_check_needs_no_api_credentials(self):
        manager=object.__new__(TelegramAuthManager)
        with patch('urllib.request.urlopen', return_value=FakeResponse()) as mocked:
            self.assertTrue(asyncio.run(manager.check_website_connection()))
        args,kwargs=mocked.call_args
        self.assertEqual(args[0].full_url, 'https://telegram.org/')
        self.assertEqual(kwargs.get('timeout'), 8)

    def test_website_failure_is_reported(self):
        manager=object.__new__(TelegramAuthManager)
        with patch('urllib.request.urlopen', side_effect=OSError('network unreachable')):
            with self.assertRaisesRegex(RuntimeError, 'Сайт telegram.org недоступен'):
                asyncio.run(manager.check_website_connection())

if __name__=='__main__': unittest.main()
