"""Local-only microscope workspace. Run: python3 server.py"""

import argparse
import json
import platform
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from camera import status
from acquisition import Acquisition
from dili import CameraError
from replay import ReplayAcquisition
from captures import CaptureStore

ROOT = Path(__file__).resolve().parent / "web"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/geometry.js": ("geometry.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}
for module in ('api', 'markers', 'overlays', 'viewer', 'inspection', 'calibration-ui', 'exports'):
    ASSETS[f'/{module}.js'] = (f'{module}.js', 'text/javascript; charset=utf-8')


def acquisition_report(service):
    acquisition = service.state()
    if acquisition['source_type'] == 'replay':
        return {'checked_at': datetime.now(timezone.utc).isoformat(),
                'platform': platform.system(), 'architecture': platform.machine(),
                'usb_state': 'not_used', 'devices': [], 'acquisition': acquisition,
                'capture_available': acquisition['driver_available'],
                'capture_state': 'replaying' if acquisition['running'] else 'ready',
                'message': acquisition['error'] or
                    f"Recorded raw data · {acquisition['dataset']} · {acquisition['recorded_frame_count']} frames in this loop. USB camera is not used."}
    report = status()
    report['acquisition'] = acquisition
    report['capture_available'] = acquisition['driver_available'] and report['usb_state'] == 'connected'
    report['capture_state'] = 'running' if acquisition['running'] else 'ready' if report['capture_available'] else 'unavailable'
    if acquisition['error']:
        report['message'] = acquisition['error']
    elif report['capture_available']:
        report['message'] = f"Experimental native SDK · {acquisition['width']} × {acquisition['height']} · {acquisition['preview']}."
    return report


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Reject unexpected Host headers, including DNS rebinding to loopback.
        if self.headers.get("Host") not in self.server.allowed_hosts:
            self.send_error(403)
            return
        try:
            self.get_route()
        except (ValueError, KeyError, TypeError) as error:
            self.respond(json.dumps({'error': str(error)}).encode(), 'application/json', 400)
        except FileNotFoundError:
            self.respond(b'{"error":"Saved item not found"}', 'application/json', 404)
        except CameraError as error:
            self.respond(json.dumps({'error': str(error)}).encode(), 'application/json', 409)
        except OSError as error:
            self.respond(json.dumps({'error': f'Cannot read local files: {error}'}).encode(), 'application/json', 500)

    def get_route(self):
        path = urlsplit(self.path).path
        response_headers = {}
        if path == "/api/status":
            report = acquisition_report(self.server.acquisition)
            payload = json.dumps(report).encode()
            content_type = "application/json"
        elif path == '/api/camera/frame.png':
            try:
                payload, metadata = self.server.acquisition.read_png(with_metadata=True)
                response_headers['X-Camera-Display'] = metadata['display_mode']
                response_headers['X-Camera-White-Balance'] = json.dumps(metadata['white_balance_gains'])
                response_headers['X-Camera-Source'] = metadata['source_type']
                response_headers['X-Frame-ID'] = metadata['frame_id']
                response_headers['X-Raw-Saturated-Percent'] = str(metadata['raw_statistics']['saturated_percent'])
                response_headers['X-Raw-Focus'] = str(metadata['raw_statistics']['focus'])
                if metadata.get('recorded_file'):
                    response_headers['X-Camera-Recorded-File'] = metadata['recorded_file']
                    response_headers['X-Camera-Exposure-Lines'] = str(metadata['exposure_lines'])
            except CameraError as error:
                self.respond(json.dumps({'error': str(error)}).encode(), 'application/json', 409)
                return
            content_type = 'image/png'
        elif path == '/api/sessions':
            payload = json.dumps(self.server.captures.list_sessions()).encode()
            content_type = 'application/json'
        elif path == '/api/profiles':
            payload = json.dumps(self.server.captures.profiles()).encode()
            content_type = 'application/json'
        elif re.fullmatch(r'/api/frames/[a-f0-9]{32}', path):
            _, metadata = self.server.acquisition.retained.get(path.rsplit('/', 1)[1])
            payload = json.dumps(metadata).encode()
            content_type = 'application/json'
        elif match := re.fullmatch(r'/api/sessions/(session-[a-zA-Z0-9-]+)/(capture-[a-f0-9]{32})(?:/([a-z.-]+))?', path):
            session_id, capture_id, kind = match.groups()
            if kind:
                payload, content_type = self.server.captures.asset(session_id, capture_id, kind)
            else:
                payload = json.dumps(self.server.captures.get(session_id, capture_id)).encode()
                content_type = 'application/json'
        elif path in ASSETS:
            filename, content_type = ASSETS[path]
            payload = (ROOT / filename).read_bytes()
        else:
            self.send_error(404)
            return
        self.respond(payload, content_type, headers=response_headers)

    def do_POST(self):
        host = self.headers.get('Host')
        origin = self.headers.get('Origin')
        if (host not in self.server.allowed_hosts or
                (origin is not None and origin != f'http://{host}') or
                self.headers.get('X-Microscope-Client') != 'local-ui'):
            self.send_error(403)
            return
        if self.headers.get('Content-Type') != 'application/json':
            self.send_error(415)
            return
        try:
            path = urlsplit(self.path).path
            length = int(self.headers.get('Content-Length', '0'))
            limit = 32*1024*1024 if path == '/api/export/png' else 256*1024 if path in ('/api/capture', '/api/annotations', '/api/profiles') else 1024
            if not 0 < length <= limit:
                raise ValueError('Invalid request length')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected a JSON object')
            if path == '/api/capture':
                frame, metadata = self.server.acquisition.retained.get(data.get('frame_id'))
                result = self.server.captures.capture(frame, metadata, data)
            elif path == '/api/annotations':
                result = self.server.captures.update(data['session_id'], data['capture_id'], data)
            elif path == '/api/profiles':
                result = self.server.captures.create_profile(data)
            elif path == '/api/export/fits':
                result = self.server.captures.export_fits(data['session_id'], data['capture_id'])
            elif path == '/api/export/png':
                result = self.server.captures.save_png(data['session_id'], data['capture_id'], data)
            elif path == '/api/camera/start':
                result = self.server.acquisition.start()
            elif path == '/api/camera/stop':
                result = self.server.acquisition.stop()
            elif path == '/api/camera/processing':
                result = self.server.acquisition.set_processing(data)
            elif path == '/api/camera/white-balance':
                if data:
                    raise ValueError('White-balance request takes an empty object')
                result = self.server.acquisition.balance_neutral()
            elif path == '/api/camera/resolution':
                if set(data) != {'resolution'}:
                    raise ValueError('Supply resolution')
                result = self.server.acquisition.set_resolution(data['resolution'])
            elif path == '/api/camera/settings':
                result = self.server.acquisition.configure(data)
            elif path == '/api/camera/recording':
                if self.server.acquisition.source_type != 'replay' or set(data) != {'recording_id'}:
                    raise ValueError('Supply recording_id in offline replay mode')
                result = self.server.acquisition.select_recording(data['recording_id'])
            else:
                self.send_error(404)
                return
        except (ValueError, UnicodeDecodeError, KeyError, TypeError) as error:
            self.respond(json.dumps({'error': str(error)}).encode(), 'application/json', 400)
            return
        except CameraError as error:
            self.respond(json.dumps({'error': str(error)}).encode(), 'application/json', 409)
            return
        except FileNotFoundError:
            self.respond(b'{"error":"Saved item not found"}', 'application/json', 404)
            return
        except OSError as error:
            self.respond(json.dumps({'error': f'Cannot save local files: {error}'}).encode(), 'application/json', 500)
            return
        self.respond(json.dumps(result).encode(), 'application/json')

    def respond(self, payload, content_type, code=200, headers=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)


def make_server(port, replay=None, sessions=None):
    acquisition = ReplayAcquisition(replay) if replay else Acquisition()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except Exception:
        acquisition.close()
        raise
    actual_port = server.server_address[1]
    server.allowed_hosts = {f"127.0.0.1:{actual_port}", f"localhost:{actual_port}"}
    server.acquisition = acquisition
    server.captures = CaptureStore(sessions or ROOT.parent/'sessions')
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--replay", type=Path, help="Replay a raw dataset directory or manifest, without USB access")
    parser.add_argument('--sessions', type=Path, help='Local inspection session directory (default: sessions/)')
    args = parser.parse_args()
    with make_server(args.port, args.replay, args.sessions) as server:
        print(f"Microscope workspace: http://127.0.0.1:{server.server_address[1]}", flush=True)
        print("Offline recorded data · no USB access." if args.replay else "Experimental native SDK · camera capture.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.acquisition.close()


if __name__ == "__main__":
    main()
