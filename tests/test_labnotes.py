from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from tools import labnotes


class MockMattermost(BaseHTTPRequestHandler):
    """Webhook at /hooks/secret123 and the few REST v4 calls the API transport uses."""
    responses = []   # queued (status, delay_seconds) for the next posts; default 200 immediately
    posts = {}
    uploads = []

    def log_message(self, *args):
        pass

    def reply(self, payload, code=200):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/api/v4/teams/name/oneworld':
            return self.reply({'id': 'team1'})
        if self.path == '/api/v4/teams/team1/channels/name/logbook-microscope':
            return self.reply({'id': 'chan1'})
        if self.path.startswith('/api/v4/channels/chan1/posts'):
            return self.reply({'order': list(self.posts), 'posts': self.posts})
        self.reply({'message': 'not found'}, 404)

    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        if self.path == '/api/v4/files':
            MockMattermost.uploads.append(body)
            return self.reply({'file_infos': [{'id': f'file{len(self.uploads)}'}]})
        code, delay = MockMattermost.responses.pop(0) if MockMattermost.responses else (200, 0)
        if code == 200:  # the post is accepted even if the response is then delayed past the client timeout
            message = json.loads(body).get('text') or json.loads(body).get('message')
            post_id = f'post{len(self.posts) + 1}'
            MockMattermost.posts[post_id] = {'id': post_id, 'message': message,
                                             'file_ids': json.loads(body).get('file_ids', [])}
        time.sleep(delay)
        if code == 200:
            return self.reply({'id': post_id} if self.path == '/api/v4/posts' else {})
        self.reply({'message': 'secret123 should never appear in errors'}, code)


class LabNotesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), MockMattermost)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.server.server_address[1]}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        MockMattermost.responses, MockMattermost.posts, MockMattermost.uploads = [], {}, []
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.dir = Path(temporary.name)
        (self.dir / 'fig.png').write_bytes(b'\x89PNG fixture')
        self.db = labnotes.outbox(self.dir / 'outbox.sqlite')
        self.addCleanup(self.db.close)

    def note(self, name='n.md', **header):
        fields = {'id': 'microscope-20260924-test', 'label': 'RUN', 'title': 'Backlit test @channel',
                  'occurred': '2026-09-24T06:02:00Z/2026-09-24T06:24:00Z', 'author': 'U.Warring',
                  'attachments': 'fig.png', **header}
        text = '---\n' + ''.join(f'{k}: {v}\n' for k, v in fields.items() if v is not None) + \
               '---\nResult for @all and @uwarring; e-mail a@b.de stays.\n'
        (self.dir / name).write_text(text)
        return labnotes.read_note(self.dir / name)

    def webhook(self):
        return labnotes.WebhookTransport({'transport': 'webhook', 'webhook_url': self.base + '/hooks/secret123'})

    def api(self):
        return labnotes.ApiTransport({'transport': 'api', 'server': self.base, 'token': 'tok', 'team': 'oneworld',
                                      'channel': 'logbook-microscope'})

    def test_render_neutralises_mentions_and_marks_late_posts_and_retries(self):
        note = self.note()
        message = labnotes.render(note, delivered_at=note['occurred'][1] + timedelta(days=2), attempt=2,
                                  file_transport=False)
        self.assertNotIn('@channel', message)
        self.assertNotIn('@all', message)
        self.assertNotIn('@uwarring', message)
        self.assertIn('a@b.de', message)  # e-mail addresses are not mentions
        self.assertIn('Event `microscope-20260924-test`', message)
        self.assertIn('2026-09-24T06:02:00Z – 2026-09-24T06:24:00Z', message)
        self.assertIn('Late post', message)
        self.assertIn('Delivery attempt 2', message)
        self.assertIn('Figures kept locally', message)
        self.assertNotIn('Late post', labnotes.render(note, delivered_at=note['occurred'][1] + timedelta(hours=1)))

    def test_large_images_must_be_previews(self):
        import struct, zlib
        def png(width, height):
            return (b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' +
                    struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0) + b'\0' * 4)
        (self.dir / 'big.png').write_bytes(png(2400, 900))
        with self.assertRaises(labnotes.NoteError) as error:
            self.note(attachments='big.png')
        self.assertIn('preview', str(error.exception))
        (self.dir / 'small.png').write_bytes(png(1280, 480))
        self.assertEqual(labnotes.image_size(self.dir / 'small.png'), (1280, 480))
        self.note(attachments='small.png')
        self.assertIsNone(labnotes.image_size(self.dir / 'fig.png'))  # not a real image header: treated as a file

    def test_invalid_notes_are_rejected(self):
        for header in ({'label': 'MISC'}, {'occurred': '2026-09-24T06:02:00'}, {'attachments': 'missing.png'},
                       {'id': 'Bad ID'}, {'occurred': '2026-09-24T07:00:00Z/2026-09-24T06:00:00Z'}):
            with self.subTest(header=header), self.assertRaises(labnotes.NoteError):
                self.note(**header)

    def test_enqueue_is_idempotent_and_refuses_silent_edits(self):
        self.assertIn('queued', labnotes.enqueue(self.db, self.note()))
        self.assertIn('already in the outbox', labnotes.enqueue(self.db, self.note()))
        with self.assertRaises(labnotes.NoteError):
            labnotes.enqueue(self.db, self.note(title='Changed title'))
        correction = self.note('c.md', id='microscope-20260924-test-correction', corrects='microscope-20260924-test')
        labnotes.enqueue(self.db, correction)
        self.assertIn('Corrects event `microscope-20260924-test`', labnotes.render(correction))

    def test_webhook_transient_and_permanent_failures(self):
        labnotes.enqueue(self.db, self.note())
        start = labnotes.now()
        MockMattermost.responses = [(503, 0)]
        self.assertIn('pending', labnotes.deliver(self.db, self.webhook(), moment=start)[0])
        self.assertEqual(labnotes.deliver(self.db, self.webhook(), moment=start), ['Nothing due.'])  # backoff
        result = labnotes.deliver(self.db, self.webhook(), moment=start + timedelta(minutes=5))
        self.assertIn('sent', result[0])
        self.assertEqual(len(MockMattermost.posts), 1)
        self.assertNotIn('secret123', ' '.join(labnotes.status(self.db)))
        labnotes.enqueue(self.db, self.note('b.md', id='microscope-20260924-second'))
        MockMattermost.responses = [(400, 0)]
        report = labnotes.deliver(self.db, self.webhook(), moment=start)
        self.assertIn('error', report[0])
        self.assertNotIn('secret123', report[0])
        self.assertEqual(labnotes.deliver(self.db, self.webhook(), moment=start + timedelta(days=1)), ['Nothing due.'])

    def test_webhook_timeout_is_uncertain_and_the_retry_is_marked(self):
        labnotes.enqueue(self.db, self.note())
        MockMattermost.responses = [(200, 1.5)]
        start = labnotes.now()
        with patch.object(labnotes, 'TIMEOUT', 0.5):
            self.assertIn('uncertain', labnotes.deliver(self.db, self.webhook(), moment=start)[0])
        time.sleep(1.2)
        labnotes.deliver(self.db, self.webhook(), moment=start + timedelta(minutes=5))
        messages = [p['message'] for p in MockMattermost.posts.values()]
        self.assertEqual(len(messages), 2)  # a webhook cannot check the channel: the duplicate is visible
        self.assertIn('Delivery attempt 2', messages[1])

    def test_api_uploads_files_and_does_not_repost_after_an_uncertain_timeout(self):
        labnotes.enqueue(self.db, self.note())
        MockMattermost.responses = [(200, 1.5)]
        start = labnotes.now()
        with patch.object(labnotes, 'TIMEOUT', 0.5):
            self.assertIn('uncertain', labnotes.deliver(self.db, self.api(), moment=start)[0])
        time.sleep(1.2)
        report = labnotes.deliver(self.db, self.api(), moment=start + timedelta(minutes=5))
        self.assertIn('found in channel, not re-posted', report[0])
        self.assertEqual(len(MockMattermost.posts), 1)
        self.assertEqual(len(MockMattermost.uploads), 1)
        self.assertEqual(next(iter(MockMattermost.posts.values()))['file_ids'], ['file1'])
        self.assertIn(b'fig.png', MockMattermost.uploads[0])

    def test_config_must_be_private(self):
        path = self.dir / 'config.json'
        path.write_text(json.dumps({'transport': 'webhook', 'webhook_url': 'https://example.invalid/hooks/abc'}))
        os.chmod(path, 0o644)
        with self.assertRaises(SystemExit):
            labnotes.load_config(path)
        os.chmod(path, 0o600)
        config = labnotes.load_config(path)
        self.assertEqual(labnotes.redact('failed at https://example.invalid/hooks/abc', config), 'failed at <redacted>')


if __name__ == '__main__':
    unittest.main()
