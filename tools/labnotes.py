"""Post dedicated microscope lab notes to the Mattermost lab-book channel through a durable outbox.

  python3 -m tools.labnotes preview IMG... --out DIR   # low-resolution JPEG previews for attachments (macOS sips)
  python3 -m tools.labnotes check NOTE.md...     # validate and print the exact message; sends nothing
  python3 -m tools.labnotes enqueue NOTE.md...   # store in the local outbox (idempotent per event ID)
  python3 -m tools.labnotes deliver [--dry-run]  # send due events; safe to re-run
  python3 -m tools.labnotes status               # queue counts, ages and last errors (secrets redacted)
  python3 -m tools.labnotes retry EVENT_ID       # re-arm an event that failed permanently

Follows the lab's lab-book conventions (lab-infrastructure, task-wavemeter-logbook.md): labels
[NOTE]/[SETTING]/[SERVICE]/[RUN], a stable event ID and the UTC occurrence time in every post,
delivery separate from the work that produced the note, no exactly-once promise (retries are
visible and, with the API transport, checked against the channel first), and broad mentions
neutralised. Notes and the outbox are local lab data (artifacts/, ignored by Git).

Credentials live outside the repository in ~/.config/microscope-labnotes/config.json (mode 600),
or the file named by MICROSCOPE_LABNOTES_CONFIG:
  {"transport": "webhook", "webhook_url": "https://.../hooks/..."}            text only
  {"transport": "api", "server": "https://...", "token": "...",               text and files
   "team": "oneworld", "channel": "logbook-microscope"}
Instead of "token", "token_file" and "token_key" read KEY=value from an existing private (mode 600)
.env file, so a secret is not copied. For shared use, prefer a channel-scoped webhook or a bot token.
The pilot (2026-09-26, operator's decision) posts from the operator's own computer with the operator's
personal access token, i.e. in the operator's name.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
import struct
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent.parent
OUTBOX = ROOT / 'artifacts' / 'labnotes' / 'outbox.sqlite'
CONFIG = Path.home() / '.config' / 'microscope-labnotes' / 'config.json'
LABELS = ('NOTE', 'SETTING', 'SERVICE', 'RUN')
MAX_MESSAGE = 16000             # Mattermost's post limit is 16383 characters
MAX_ATTACHMENTS = 5
MAX_ATTACHMENT_BYTES = 20 * 2**20
MAX_IMAGE_SIDE = 1600           # images are inline previews; full-resolution figures stay in the local packet
MAX_IMAGE_BYTES = 2**20
PREVIEW_SIDE = 1280
LATE_AFTER = timedelta(hours=6)  # posts delivered later than this after the event say so
TIMEOUT = 30
SOURCE = 'microscope labnotes'


class NoteError(ValueError):
    pass


class DeliveryError(RuntimeError):
    """kind: 'transient' (retry later), 'permanent' (needs `retry`) or 'uncertain' (may have posted)."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def now():
    return datetime.now(timezone.utc)


def iso(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def parse_time(text):
    moment = datetime.fromisoformat(text.strip().replace('Z', '+00:00'))
    if moment.tzinfo is None:
        raise NoteError(f'Time without time zone: {text!r}; use UTC with a trailing Z')
    return moment.astimezone(timezone.utc)


# --- Notes -------------------------------------------------------------------------------------
def read_note(path):
    path = Path(path)
    text = path.read_text()
    if not text.startswith('---\n') or '\n---\n' not in text[4:]:
        raise NoteError(f'{path}: a note starts with a --- header block')
    header_text, body = text[4:].split('\n---\n', 1)
    header = {}
    for line in header_text.splitlines():
        if line.strip():
            key, sep, value = line.partition(':')
            if not sep:
                raise NoteError(f'{path}: header line without "key: value": {line!r}')
            header[key.strip()] = value.strip()
    unknown = set(header) - {'id', 'label', 'title', 'occurred', 'author', 'attachments', 'corrects'}
    if unknown:
        raise NoteError(f'{path}: unknown header keys {sorted(unknown)}')
    for key in ('id', 'label', 'title', 'occurred', 'author'):
        if not header.get(key):
            raise NoteError(f'{path}: header needs {key}')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{2,100}', header['id']):
        raise NoteError(f'{path}: id uses lowercase letters, digits, dots and hyphens')
    if header['label'] not in LABELS:
        raise NoteError(f'{path}: label must be one of {", ".join(LABELS)}')
    times = [parse_time(t) for t in header['occurred'].split('/')]
    if len(times) > 2 or (len(times) == 2 and times[1] < times[0]):
        raise NoteError(f'{path}: occurred is one UTC time or start/end')
    attachments = [(path.parent / a.strip()).resolve() for a in header.get('attachments', '').split(',') if a.strip()]
    if len(attachments) > MAX_ATTACHMENTS:
        raise NoteError(f'{path}: at most {MAX_ATTACHMENTS} attachments')
    for a in attachments:
        if not a.is_file() or a.stat().st_size > MAX_ATTACHMENT_BYTES:
            raise NoteError(f'{path}: attachment missing or larger than 20 MB: {a.name}')
        size = image_size(a)
        if size and (max(size) > MAX_IMAGE_SIDE or a.stat().st_size > MAX_IMAGE_BYTES):
            raise NoteError(f'{path}: {a.name} is {size[0]} x {size[1]} px, {a.stat().st_size // 1024} KB; attach a '
                            f'low-resolution preview instead (labnotes preview, <= {MAX_IMAGE_SIDE} px and 1 MB)')
    return {'id': header['id'], 'label': header['label'], 'title': header['title'], 'occurred': times,
            'author': header['author'], 'corrects': header.get('corrects'), 'body': body.strip(),
            'attachments': [str(a) for a in attachments], 'path': str(path.resolve())}


def image_size(path):
    """(width, height) of a PNG or JPEG, or None for other files."""
    data = Path(path).read_bytes()
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', data[16:24])
    if data[:2] == b'\xff\xd8':
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                break
            marker, length = data[i + 1], struct.unpack('>H', data[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack('>HH', data[i + 5:i + 9])
                return width, height
            i += 2 + length
    return None


def make_preview(source, out_dir, side=PREVIEW_SIDE):
    """Write a JPEG no larger than `side` pixels next to nothing else; the source file is only read."""
    source, out_dir = Path(source), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f'{source.stem}-preview.jpg'
    subprocess.run(['sips', '-Z', str(side), '-s', 'format', 'jpeg', '-s', 'formatOptions', '80',
                    str(source), '--out', str(target)], check=True, capture_output=True)
    return target


def neutralise_mentions(text):
    """Break every @mention (including @channel/@all/@here) so a lab note never notifies anyone."""
    return re.sub(r'(?<![\w`])@(?=[A-Za-z0-9_.-])', '@​', text)


def render(note, delivered_at=None, attempt=1, file_transport=True):
    start, end = note['occurred'][0], note['occurred'][-1]
    when = f'{iso(start)}' if start == end else f'{iso(start)} – {iso(end)}'
    lines = [f"#### [{note['label']}] {neutralise_mentions(note['title'])}",
             f"Event `{note['id']}` · occurred {when} · author {neutralise_mentions(note['author'])} "
             f"(self-reported) · via {SOURCE}"]
    if note['corrects']:
        lines.append(f"Corrects event `{note['corrects']}`.")
    if delivered_at and delivered_at - end > LATE_AFTER:
        lines.append(f"_Late post: delivered {iso(delivered_at)}, after the event._")
    if attempt > 1:
        lines.append(f"_Delivery attempt {attempt}; an earlier attempt may also have posted this event._")
    lines += ['', neutralise_mentions(note['body'])]
    if note['attachments'] and not file_transport:
        names = ', '.join(Path(a).name for a in note['attachments'])
        lines += ['', f'_Figures kept locally (webhook posts carry no files): {names}_']
    message = '\n'.join(lines)
    if len(message) > MAX_MESSAGE:
        raise NoteError(f"{note['id']}: message has {len(message)} characters; the limit is {MAX_MESSAGE}")
    return message


# --- Outbox ------------------------------------------------------------------------------------
def outbox(path=None):
    path = Path(path or os.environ.get('MICROSCOPE_LABNOTES_OUTBOX') or OUTBOX)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY, note_json TEXT NOT NULL, content_sha256 TEXT NOT NULL, enqueued_at TEXT NOT NULL,
        status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT, last_attempt_at TEXT,
        last_error TEXT, delivered_at TEXT, post_id TEXT, transport TEXT)""")
    return db


def content_hash(note):
    stable = {k: note[k] for k in ('id', 'label', 'title', 'author', 'corrects', 'body')}
    stable['occurred'] = [iso(t) for t in note['occurred']]
    stable['attachments'] = [hashlib.sha256(Path(a).read_bytes()).hexdigest() for a in note['attachments']]
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


def enqueue(db, note):
    digest = content_hash(note)
    row = db.execute('SELECT content_sha256, status FROM events WHERE id = ?', (note['id'],)).fetchone()
    if row:
        if row['content_sha256'] != digest:
            raise NoteError(f"Event {note['id']} is already in the outbox with different content. Posts are not "
                            'edited in place: write a new note with a new id and "corrects: ' + note['id'] + '".')
        return f"{note['id']}: already in the outbox ({row['status']})"
    stored = dict(note, occurred=[iso(t) for t in note['occurred']])
    db.execute('INSERT INTO events (id, note_json, content_sha256, enqueued_at, status) VALUES (?, ?, ?, ?, ?)',
               (note['id'], json.dumps(stored), digest, iso(now()), 'pending'))
    db.commit()
    return f"{note['id']}: queued"


def stored_note(row):
    note = json.loads(row['note_json'])
    note['occurred'] = [parse_time(t) for t in note['occurred']]
    return note


# --- Transports --------------------------------------------------------------------------------
def load_config(path=None):
    path = Path(path or os.environ.get('MICROSCOPE_LABNOTES_CONFIG') or CONFIG)
    if not path.is_file():
        raise SystemExit(f'No delivery configuration at {path}. See the module docstring; nothing was sent.')
    if path.stat().st_mode & 0o077:
        raise SystemExit(f'{path} is readable by others; run: chmod 600 {path}')
    config = json.loads(path.read_text())
    if config.get('token_file'):
        token_file = Path(config['token_file']).expanduser()
        if not token_file.is_file():
            raise SystemExit(f'Token file not found: {token_file}')
        if token_file.stat().st_mode & 0o077:
            raise SystemExit(f'{token_file} is readable by others; run: chmod 600 {token_file}')
        key = config.get('token_key') or 'MATTERMOST_TOKEN'
        for line in token_file.read_text().splitlines():
            name, sep, value = line.partition('=')
            if sep and name.strip() == key:
                config['token'] = value.strip().strip('"\'')
        if not config.get('token'):
            raise SystemExit(f'{key} not found in {token_file}')
    if config.get('transport') == 'webhook' and str(config.get('webhook_url', '')).startswith('https://'):
        return config
    if config.get('transport') == 'api' and all(config.get(k) for k in ('server', 'token', 'team', 'channel')):
        return config
    raise SystemExit(f'{path}: need transport "webhook" with an https webhook_url, or "api" with server, token, team, channel')


def redact(text, config):
    webhook_key = str(config.get('webhook_url') or '').rstrip('/').rsplit('/', 1)[-1] or None
    for secret in (config.get('webhook_url'), config.get('token'), webhook_key):
        if secret:
            text = str(text).replace(secret, '<redacted>')
    return re.sub(r'/hooks/[A-Za-z0-9]+', '/hooks/<redacted>', str(text))


def http(method, url, config, body=None, headers=None):
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = response.read()
            return json.loads(payload) if payload[:1] in (b'{', b'[') else payload.decode(errors='replace')
    except urllib.error.HTTPError as error:
        detail = redact(error.read()[:300].decode(errors='replace'), config)
        kind = 'transient' if error.code == 429 or error.code >= 500 else 'permanent'
        raise DeliveryError(kind, f'HTTP {error.code}: {detail}') from None
    except TimeoutError:
        # The server may have accepted the post before the response was lost.
        raise DeliveryError('uncertain', 'timed out waiting for the response') from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise DeliveryError('uncertain', 'timed out waiting for the response') from None
        raise DeliveryError('transient', f'connection failed: {redact(error.reason, config)}') from None


class WebhookTransport:
    files = False

    def __init__(self, config):
        self.config = config

    def already_posted(self, event_id):
        return None  # a webhook cannot read the channel

    def post(self, message, attachments):
        http('POST', self.config['webhook_url'], self.config, json.dumps({'text': message}).encode(),
             {'Content-Type': 'application/json'})
        return None


class ApiTransport:
    files = True

    def __init__(self, config):
        self.config = config
        self.api = config['server'].rstrip('/') + '/api/v4'
        self.auth = {'Authorization': f"Bearer {config['token']}"}
        self._channel = None

    def call(self, method, path, body=None, headers=None):
        return http(method, self.api + path, self.config, body, {**self.auth, **(headers or {})})

    def channel(self):
        if not self._channel:
            team = self.call('GET', f"/teams/name/{self.config['team']}")
            self._channel = self.call('GET', f"/teams/{team['id']}/channels/name/{self.config['channel']}")['id']
        return self._channel

    def already_posted(self, event_id):
        posts = self.call('GET', f'/channels/{self.channel()}/posts?per_page=200')
        marker = f'Event `{event_id}`'
        return next((pid for pid, p in posts.get('posts', {}).items() if marker in p.get('message', '')), None)

    def upload(self, path):
        boundary = uuid.uuid4().hex
        path = Path(path)
        kind = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="channel_id"\r\n\r\n{self.channel()}\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{path.name}"\r\n'
                f'Content-Type: {kind}\r\n\r\n').encode() + path.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
        info = self.call('POST', '/files', body, {'Content-Type': f'multipart/form-data; boundary={boundary}'})
        return [f['id'] for f in info.get('file_infos', [])]

    def post(self, message, attachments):
        file_ids = [fid for a in attachments for fid in self.upload(a)]
        result = self.call('POST', '/posts', json.dumps({'channel_id': self.channel(), 'message': message,
                                                          'file_ids': file_ids}).encode(),
                           {'Content-Type': 'application/json'})
        return result.get('id')


def transport_for(config):
    return ApiTransport(config) if config['transport'] == 'api' else WebhookTransport(config)


# --- Delivery ----------------------------------------------------------------------------------
def backoff(attempts):
    return timedelta(seconds=min(3600, 30 * 2 ** max(0, attempts - 1)))


def deliver(db, transport, dry_run=False, moment=None):
    moment = moment or now()
    rows = db.execute("SELECT * FROM events WHERE status IN ('pending', 'uncertain') "
                      "AND (next_attempt_at IS NULL OR next_attempt_at <= ?) ORDER BY enqueued_at", (iso(moment),)).fetchall()
    report = []
    for row in rows:
        note = stored_note(row)
        attempt = row['attempts'] + 1
        message = render(note, delivered_at=moment, attempt=attempt, file_transport=transport.files)
        if dry_run:
            report.append(f"{row['id']}: would send attempt {attempt} ({len(message)} characters, "
                          f"{len(note['attachments']) if transport.files else 0} files)")
            continue
        try:
            existing = transport.already_posted(row['id']) if row['attempts'] else None
            post_id = existing or transport.post(message, note['attachments'] if transport.files else [])
            db.execute("UPDATE events SET status='sent', attempts=?, last_attempt_at=?, delivered_at=?, post_id=?, "
                       "transport=?, last_error=NULL, next_attempt_at=NULL WHERE id=?",
                       (attempt, iso(moment), iso(moment), post_id, type(transport).__name__, row['id']))
            report.append(f"{row['id']}: {'found in channel, not re-posted' if existing else 'sent'}")
        except DeliveryError as error:
            status = {'transient': 'pending', 'uncertain': 'uncertain', 'permanent': 'error'}[error.kind]
            retry_at = iso(moment + backoff(attempt)) if status != 'error' else None
            db.execute('UPDATE events SET status=?, attempts=?, last_attempt_at=?, last_error=?, next_attempt_at=? WHERE id=?',
                       (status, attempt, iso(moment), str(error), retry_at, row['id']))
            report.append(f"{row['id']}: {status} ({error})" + (f'; next try after {retry_at}' if retry_at else ''))
        db.commit()
    return report or ['Nothing due.']


def status(db, moment=None):
    moment = moment or now()
    lines = [f"{r['status']}: {r['n']}" for r in db.execute('SELECT status, COUNT(*) n FROM events GROUP BY status')]
    for r in db.execute("SELECT id, status, enqueued_at, attempts, last_error, next_attempt_at, post_id FROM events "
                        "ORDER BY enqueued_at"):
        age = moment - parse_time(r['enqueued_at'])
        detail = f"post {r['post_id']}" if r['post_id'] else (r['last_error'] or '')
        lines.append(f"  {r['id']}  {r['status']}  attempts {r['attempts']}  queued {age.days}d "
                     f"{age.seconds // 3600}h ago  {detail}".rstrip())
    return lines or ['Outbox is empty.']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--outbox', help=argparse.SUPPRESS)
    parser.add_argument('--config', help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('check', 'enqueue'):
        commands.add_parser(name).add_argument('notes', nargs='+')
    preview = commands.add_parser('preview')
    preview.add_argument('images', nargs='+')
    preview.add_argument('--out', required=True)
    preview.add_argument('--side', type=int, default=PREVIEW_SIDE)
    commands.add_parser('deliver').add_argument('--dry-run', action='store_true')
    commands.add_parser('status')
    commands.add_parser('retry').add_argument('event_id')
    args = parser.parse_args(argv)
    try:
        if args.command == 'preview':
            for image in args.images:
                target = make_preview(image, args.out, args.side)
                width, height = image_size(target)
                print(f'{target}  {width} x {height} px  {target.stat().st_size // 1024} KB')
            return 0
        if args.command == 'check':
            for path in args.notes:
                note = read_note(path)
                files = ', '.join(f'{Path(a).name} ({Path(a).stat().st_size // 1024} KB)' for a in note['attachments'])
                print(f"--- {note['id']} ({len(note['attachments'])} attachments: {files or 'none'})")
                print(render(note, delivered_at=now()))
            return 0
        db = outbox(args.outbox)
        if args.command == 'enqueue':
            for path in args.notes:
                print(enqueue(db, read_note(path)))
        elif args.command == 'deliver':
            config = load_config(args.config)
            for line in deliver(db, transport_for(config), args.dry_run):
                print(redact(line, config))
        elif args.command == 'status':
            print('\n'.join(status(db)))
        elif args.command == 'retry':
            changed = db.execute("UPDATE events SET status='pending', next_attempt_at=NULL WHERE id=? AND status='error'",
                                 (args.event_id,)).rowcount
            db.commit()
            print(f'{args.event_id}: re-armed' if changed else f'{args.event_id}: not in error state')
        return 0
    except NoteError as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
