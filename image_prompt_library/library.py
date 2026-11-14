import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, ImageOps

from .duplicates import DuplicateJobs
from .extractor import VERSION, NO_METADATA, extract, normalize, read_metadata


EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def default_home():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "WorkflowX" / "ImagePromptLibrary"


class Library:
    def __init__(self, home):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "thumbnails").mkdir(exist_ok=True)
        self.database = self.home / "library.sqlite3"
        self.lock = threading.Lock()
        self.job = {"state": "idle", "processed": 0, "updated": 0, "skipped": 0, "errors": []}
        self.cancel = threading.Event()
        if self.database.exists():
            with self.connect() as existing:
                if not existing.execute("SELECT name FROM sqlite_master WHERE name='blacklist'").fetchone():
                    with sqlite3.connect(self.home / 'before-blacklist-migration.sqlite3') as backup:
                        existing.backup(backup)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, stamp TEXT NOT NULL,
                positive TEXT NOT NULL, group_id TEXT, status TEXT NOT NULL,
                extraction TEXT NOT NULL, correction TEXT, updated REAL NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS image_groups ON images(group_id)")
            db.execute("CREATE TABLE IF NOT EXISTS blacklist (group_id TEXT PRIMARY KEY, positive TEXT UNIQUE NOT NULL, created REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS library_settings (key TEXT PRIMARY KEY, value REAL NOT NULL)")
            db.execute("INSERT OR IGNORE INTO library_settings VALUES ('revision',0)")
            db.execute("INSERT OR IGNORE INTO library_settings VALUES ('threshold',90)")
            db.execute("CREATE VIEW IF NOT EXISTS visible_images AS SELECT * FROM images WHERE NOT EXISTS (SELECT 1 FROM blacklist WHERE blacklist.positive=images.positive)")
            for table in ('images', 'blacklist'):
                for action in ('INSERT', 'UPDATE', 'DELETE'):
                    db.execute(f"CREATE TRIGGER IF NOT EXISTS revision_{table}_{action} AFTER {action} ON {table} BEGIN UPDATE library_settings SET value=value+1 WHERE key='revision'; END")
            for row in db.execute("SELECT id,extraction FROM images WHERE status='review'").fetchall():
                if json.loads(row['extraction']).get('issues') == [NO_METADATA]:
                    db.execute("UPDATE images SET status='ignored',group_id=NULL WHERE id=?", (row['id'],))

        self.duplicates = DuplicateJobs(self)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def snapshot(self):
        with self.lock:
            return dict(self.job, errors=list(self.job["errors"]))

    def revision(self, db):
        return int(db.execute("SELECT value FROM library_settings WHERE key='revision'").fetchone()[0])

    def settings(self, threshold=...):
        if threshold is not ... and (type(threshold) not in (int, float) or not 1 <= threshold <= 100):
            raise ValueError('Similarity must be a number from 1 to 100')
        with self.connect() as db:
            if threshold is not ...:
                db.execute("UPDATE library_settings SET value=? WHERE key='threshold'", (threshold,))
            return {'threshold': db.execute("SELECT value FROM library_settings WHERE key='threshold'").fetchone()[0]}

    def blacklisted(self, query='', page=0):
        pattern = '%' + query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        with self.connect() as db:
            total = db.execute("SELECT count(*) FROM blacklist WHERE positive LIKE ? ESCAPE '\\'", (pattern,)).fetchone()[0]
            rows = db.execute("""SELECT b.group_id,b.positive,count(i.id) AS count,min(i.id) AS id
                FROM blacklist b LEFT JOIN images i ON i.positive=b.positive
                WHERE b.positive LIKE ? ESCAPE '\\' GROUP BY b.group_id ORDER BY b.created DESC LIMIT 60 OFFSET ?""",
                (pattern, page*60)).fetchall()
            counts = dict(db.execute('SELECT status,count(*) FROM visible_images GROUP BY status').fetchall())
            counts['blacklisted'] = db.execute('SELECT count(*) FROM images WHERE positive IN (SELECT positive FROM blacklist)').fetchone()[0]
        return {'items': [dict(r) for r in rows], 'total': total, 'page': page, 'counts': counts}

    def blacklist_prompt(self, group, keep=None, job_id=None, revision=None):
        if not isinstance(group, str) or len(group) != 64:
            raise ValueError('Invalid prompt group')
        if keep is not None:
            snapshot = self.duplicates.snapshot()
            if snapshot['state'] != 'complete' or snapshot['id'] != job_id or snapshot['revision'] != revision:
                raise ValueError('Duplicate results changed. Run detection again.')
            with self.duplicates.lock:
                if not any({group, keep} == {a, b} for _, a, b in self.duplicates.pairs):
                    raise ValueError('This pair is no longer a duplicate suggestion')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            before = self.revision(db)
            if keep is not None and (revision != before or keep == group or not db.execute(
                    'SELECT 1 FROM visible_images WHERE group_id=?', (keep,)).fetchone()):
                raise ValueError('Duplicate results changed. Run detection again.')
            existing = db.execute('SELECT positive FROM blacklist WHERE group_id=?', (group,)).fetchone()
            row = existing or db.execute('SELECT positive FROM visible_images WHERE group_id=?', (group,)).fetchone()
            if not row:
                raise ValueError('Prompt group no longer exists')
            db.execute('INSERT OR IGNORE INTO blacklist VALUES (?,?,?)', (group, row['positive'], time.time()))
            count = db.execute('SELECT count(*) FROM images WHERE positive=?', (row['positive'],)).fetchone()[0]
            after = self.revision(db)
        self.duplicates.prune(group, before, after)
        return {'blacklisted_count': count, 'revision': after}

    def restore_prompt(self, group):
        if not isinstance(group, str) or len(group) != 64:
            raise ValueError('Invalid prompt group')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT positive FROM blacklist WHERE group_id=?', (group,)).fetchone()
            count = db.execute('SELECT count(*) FROM images WHERE positive=?', (row['positive'],)).fetchone()[0] if row else 0
            db.execute('DELETE FROM blacklist WHERE group_id=?', (group,))
        return {'restored_count': count}

    def refresh_existing(self):
        with self.connect() as db:
            paths = [Path(row['path']) for row in db.execute("SELECT path FROM images WHERE stamp NOT LIKE ?", (f'%:{VERSION}',))]
        if not paths:
            return
        with self.lock:
            if self.job['state'] == 'running':
                return
            self.cancel.clear()
            self.job = {"state": "running", "path": "Refreshing indexed images", "processed": 0,
                        "updated": 0, "skipped": 0, "errors": []}
        threading.Thread(target=self.scan, args=(self.home, False, paths), daemon=True).start()

    def start(self, path, recursive=True):
        path = Path(path).expanduser().resolve()
        if not path.exists():
            raise ValueError("Image or folder does not exist")
        if path.is_file() and path.suffix.lower() not in EXTENSIONS:
            raise ValueError("Choose a PNG, JPEG, WebP, or folder")
        with self.lock:
            if self.job["state"] == "running":
                raise ValueError("A scan is already running")
            self.cancel.clear()
            self.job = {"state": "running", "path": str(path), "processed": 0, "updated": 0,
                        "skipped": 0, "errors": []}
        threading.Thread(target=self.scan, args=(path, recursive), daemon=True).start()
        return self.snapshot()

    def scan(self, path, recursive, existing_paths=None):
        try:
            paths = existing_paths if existing_paths is not None else [path] if path.is_file() else path.rglob("*") if recursive else path.glob("*")
            for item in paths:
                if self.cancel.is_set():
                    break
                if item.resolve().is_relative_to(self.home.resolve()):
                    continue
                if not item.is_file() or item.suffix.lower() not in EXTENSIONS:
                    continue
                try:
                    changed = self.index(item)
                    with self.lock:
                        self.job["updated" if changed else "skipped"] += 1
                except Exception as error:
                    # A broken image must not abort a folder scan.
                    with self.lock:
                        self.job["errors"].append({"path": str(item), "error": str(error)})
                with self.lock:
                    self.job["processed"] += 1
        except Exception as error:
            with self.lock:
                self.job["errors"].append({"path": str(path), "error": str(error)})
        finally:
            with self.lock:
                self.job["state"] = "cancelled" if self.cancel.is_set() else "complete"

    def index(self, path):
        path = Path(os.path.normcase(str(path.resolve())))
        stat = path.stat()
        stamp = f"{stat.st_mtime_ns}:{stat.st_size}:{VERSION}"
        with self.connect() as db:
            previous = db.execute("SELECT * FROM images WHERE path=?", (str(path),)).fetchone()
            if previous and previous["stamp"] == stamp:
                return False
        try:
            result = extract(read_metadata(path))
        except Exception as error:
            result = {"positive": "", "stages": [], "issues": [f"Cannot read metadata: {error}"]}
        positive = normalize(result["positive"])
        status = "ignored" if result.get("skip_reason") == "no_metadata" else "review" if result["issues"] else "complete"
        same_source = previous and previous['stamp'].rsplit(':', 1)[0] == stamp.rsplit(':', 1)[0]
        correction = previous['correction'] if same_source else None
        if correction is not None:
            positive, status = correction, 'corrected'
        if same_source and previous['status'] == 'dismissed':
            status = 'dismissed'
        group = hashlib.sha256(positive.encode()).hexdigest() if status == "complete" else None
        if status == 'corrected':
            group = hashlib.sha256(positive.encode()).hexdigest()
        with self.connect() as db:
            db.execute("""INSERT INTO images(path,stamp,positive,group_id,status,extraction,updated,correction)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET stamp=excluded.stamp,
                positive=excluded.positive,group_id=excluded.group_id,status=excluded.status,
                extraction=excluded.extraction,correction=excluded.correction,updated=excluded.updated""",
                       (str(path), stamp, positive, group, status, json.dumps(result), time.time(), correction))
            row = db.execute("SELECT id FROM images WHERE path=?", (str(path),)).fetchone()
        if same_source:
            return True
        thumb = self.home / "thumbnails" / f"{row['id']}.jpg"
        thumb.unlink(missing_ok=True)
        try:
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail((384, 384))
                image.convert("RGB").save(thumb, quality=85)
        except (OSError, ValueError, Image.DecompressionBombError):
            pass
        return True

    def listing(self, query="", page=0, review=False):
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        with self.connect() as db:
            if review:
                where = "status='review' AND (positive LIKE ? ESCAPE '\\' OR path LIKE ? ESCAPE '\\')"
                total = db.execute(f"SELECT count(*) FROM visible_images WHERE {where}", (pattern, pattern)).fetchone()[0]
                rows = db.execute(f"SELECT * FROM visible_images WHERE {where} ORDER BY updated DESC LIMIT 60 OFFSET ?",
                                  (pattern, pattern, page * 60)).fetchall()
                items = [self.serialize(row) for row in rows]
            else:
                where = "group_id IS NOT NULL AND (positive LIKE ? ESCAPE '\\' OR path LIKE ? ESCAPE '\\')"
                matches = f"SELECT DISTINCT group_id FROM visible_images WHERE {where}"
                total = db.execute(f"SELECT count(*) FROM ({matches})", (pattern, pattern)).fetchone()[0]
                rows = db.execute(f"""SELECT group_id,positive,count(*) AS count,min(id) AS id
                    FROM visible_images WHERE group_id IN ({matches}) GROUP BY group_id
                    ORDER BY max(updated) DESC LIMIT 60 OFFSET ?""", (pattern, pattern, page * 60)).fetchall()
                items = [dict(row) for row in rows]
                for item in items:
                    candidates = db.execute("SELECT id,path FROM visible_images WHERE group_id=? ORDER BY id", (item["group_id"],))
                    for candidate in candidates:
                        if Path(candidate["path"]).is_file():
                            item["id"] = candidate["id"]
                            break
            counts = dict(db.execute("SELECT status,count(*) FROM visible_images GROUP BY status").fetchall())
            counts['blacklisted'] = db.execute("SELECT count(*) FROM images WHERE positive IN (SELECT positive FROM blacklist)").fetchone()[0]
        return {"items": items, "total": total, "page": page, "counts": counts}

    def serialize(self, row):
        item = dict(row)
        item["extraction"] = json.loads(item["extraction"])
        item["missing"] = not Path(item["path"]).is_file()
        item["folder"] = str(Path(item["path"]).parent)
        return item

    def get(self, image_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM images WHERE id=?", (image_id,)).fetchone()
        if not row:
            raise ValueError("Image not found")
        return self.serialize(row)

    def images(self, group, page):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM visible_images WHERE group_id=? ORDER BY id LIMIT 60 OFFSET ?", (group, page * 60)).fetchall()
            total = db.execute("SELECT count(*) FROM visible_images WHERE group_id=?", (group,)).fetchone()[0]
        return {"items": [self.serialize(row) for row in rows], "total": total, "page": page}

    def ignore(self, image_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT status,positive FROM images WHERE id=?", (image_id,)).fetchone()
            if not row:
                raise ValueError("Image not found")
            if row['status'] not in ('review', 'dismissed'):
                raise ValueError("Only images needing review can be ignored")
            cursor = db.execute("""UPDATE images SET status='dismissed',group_id=NULL,updated=?
                WHERE status='review' AND (id=? OR (? != '' AND positive=?))""",
                (time.time(), image_id, row['positive'], row['positive']))
            ignored = cursor.rowcount
        result = self.get(image_id)
        result['ignored_count'] = ignored
        return result

    def correct(self, image_id, text):
        text = normalize(text)
        if not text:
            raise ValueError("Enter the full positive prompt")
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            source = db.execute('SELECT positive,status FROM images WHERE id=?', (image_id,)).fetchone()
            if not source:
                raise ValueError('Image not found')
            if db.execute("SELECT 1 FROM blacklist WHERE positive IN (?,?)", (text, source['positive'])).fetchone():
                raise ValueError('Restore this prompt from Blacklist before accepting it')
            # Match stored normalized text, never empty/unknown prompts or ignored entries.
            original = source['positive'] if source['status'] == 'review' else ''
            cursor = db.execute("""UPDATE images SET positive=?,correction=?,group_id=?,status='corrected',updated=?
                WHERE id=? OR (status='review' AND ? != '' AND positive IN (?,?))""",
                (text, text, hashlib.sha256(text.encode()).hexdigest(), time.time(), image_id,
                 original, original, text))
            accepted = cursor.rowcount
        result = self.get(image_id)
        result['accepted_count'] = accepted
        return result
