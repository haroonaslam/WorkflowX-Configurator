import argparse
import json
import mimetypes
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .library import Library, default_home


STATIC = Path(__file__).parent / "static"


def make_server(library, token, port=0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, data, status=200, content_type="application/json"):
            body = json.dumps(data).encode() if content_type == "application/json" else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def dispatch(self, post=False):
            parts = urlsplit(self.path)
            query = parse_qs(parts.query)
            route = parts.path
            origin = f"http://127.0.0.1:{self.server.server_port}"
            source = urlsplit(self.headers.get("Origin", origin))
            if self.headers.get("Host") != origin.removeprefix("http://") or source.scheme != "http" or source.hostname != "127.0.0.1":
                self.send({"error": "Origin rejected"}, 403)
                return
            if route in ("/", "/app.js", "/style.css") and not post:
                file = STATIC / {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[route]
                self.send(file.read_bytes(), content_type={".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css"}[file.suffix])
                return
            supplied = self.headers.get("X-Library-Token", query.get("token", [""])[0])
            if not secrets.compare_digest(supplied, token):
                self.send({"error": "Launch the app using its launcher or XPrompts"}, 403)
                return
            body = {}
            if post:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 <= size <= 2_000_000:
                    raise ValueError("Request too large")
                body = json.loads(self.rfile.read(size) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("Expected a JSON object")
            page = max(0, int(query.get("page", [0])[0]))
            if route == "/api/health" and not post:
                self.send({"app": "workflowx-image-prompt-library", "version": 1})
            elif route == "/api/scan":
                self.send(library.start(body.get("path", ""), body.get("recursive", True)) if post else library.snapshot())
            elif route == "/api/cancel" and post:
                library.cancel.set()
                self.send(library.snapshot())
            elif route == "/api/prompts" and not post:
                self.send(library.listing(query.get("q", [""])[0], page, query.get("review") == ["1"]))
            elif route == "/api/images" and not post:
                self.send(library.images(query.get("group", [""])[0], page))
            elif route == "/api/correct" and post:
                self.send(library.correct(int(body["id"]), body["text"]))
            elif route == "/api/ignore" and post:
                self.send(library.ignore(int(body["id"])))
            elif route == '/api/settings':
                self.send(library.settings(body['threshold']) if post else library.settings())
            elif route == '/api/blacklist':
                self.send(library.blacklist_prompt(body['group'], body.get('keep'), body.get('job_id'), body.get('revision'))
                          if post else library.blacklisted(query.get('q', [''])[0], page))
            elif route == '/api/blacklist/restore' and post:
                self.send(library.restore_prompt(body['group']))
            elif route == '/api/duplicates':
                self.send(library.duplicates.start(body['threshold']) if post else library.duplicates.snapshot(page))
            elif route == '/api/duplicates/cancel' and post:
                library.duplicates.cancel.set()
                self.send(library.duplicates.snapshot())
            elif route == "/api/browse" and not post:
                raw = query.get("path", [str(Path.home())])[0]
                path = Path(raw).expanduser().resolve()
                if not path.is_dir():
                    raise ValueError("Folder not found")
                items = []
                for child in path.iterdir():
                    if child.is_dir() or child.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                        items.append({"name": child.name, "path": str(child), "folder": child.is_dir()})
                self.send({"path": str(path), "parent": str(path.parent), "items": sorted(items, key=lambda x: (not x["folder"], x["name"].lower()))})
            elif route in ("/api/image", "/api/thumbnail") and not post:
                record = library.get(int(query["id"][0]))
                path = Path(record["path"]) if route == "/api/image" else library.home / "thumbnails" / f"{record['id']}.jpg"
                if not path.is_file():
                    self.send({"error": "Image unavailable"}, 404)
                else:
                    self.send(path.read_bytes(), content_type=mimetypes.guess_type(str(path))[0] or "application/octet-stream")
            elif route == "/api/quit" and post:
                library.cancel.set()
                library.duplicates.cancel.set()
                self.send({"stopped": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self.send({"error": "Not found"}, 404)

        def do_GET(self):
            self.handle_request(False)

        def do_POST(self):
            self.handle_request(True)

        def handle_request(self, post):
            try:
                self.dispatch(post)
            except (ValueError, KeyError, TypeError, OSError) as error:
                self.send({"error": str(error)}, 400)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, default=default_home())
    args = parser.parse_args()
    args.home.mkdir(parents=True, exist_ok=True)
    # The server owns this OS lock for its lifetime, including simultaneous launches.
    lock = (args.home / "server.lock").open("a+b")
    lock.seek(0, 2)
    if lock.tell() == 0:
        lock.write(b"0")
        lock.flush()
    lock.seek(0)
    try:
        if __import__("os").name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        return
    token = secrets.token_urlsafe(32)
    library = Library(args.home)
    server = make_server(library, token)
    session = args.home / "session.json"
    pending = args.home / "session.tmp"
    pending.write_text(json.dumps({"port": server.server_port, "token": token}), encoding="utf-8")
    pending.replace(session)
    library.refresh_existing()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        session.unlink(missing_ok=True)
        lock.close()


if __name__ == "__main__":
    main()
