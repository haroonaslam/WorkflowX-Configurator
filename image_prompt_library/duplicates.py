"""Local, cancellable text comparisons; no generation or network calls."""
import re
import threading
import uuid
from difflib import SequenceMatcher


def tokens(text):
    return re.findall(r'\w+|[^\w\s]', text.casefold(), re.UNICODE)


def similarity(a, b):
    return 50 * (SequenceMatcher(None, a, b, autojunk=False).ratio()
                 + SequenceMatcher(None, b, a, autojunk=False).ratio())


def differences(a, b):
    left, right = re.findall(r'\s+|\w+|[^\w\s]', a), re.findall(r'\s+|\w+|[^\w\s]', b)
    parts = [[], []]
    for tag, i, j, k, l in SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
        for side, text in enumerate((''.join(left[i:j]), ''.join(right[k:l]))):
            if text:
                parts[side].append({'text': text, 'changed': tag != 'equal'})
    return parts


class DuplicateJobs:
    def __init__(self, library):
        self.library = library
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.job = {'state': 'idle', 'id': None, 'processed': 0, 'total': 0}
        self.pairs = []
        self.groups = {}

    def start(self, threshold):
        threshold = self.library.settings(threshold)['threshold']
        with self.lock:
            if self.job['state'] == 'running':
                raise ValueError('Duplicate detection is already running')
            with self.library.connect() as db:
                db.execute('BEGIN')
                revision = self.library.revision(db)
                groups = [dict(r) for r in db.execute('''SELECT group_id,positive,min(id) AS id,count(*) AS count
                    FROM visible_images WHERE group_id IS NOT NULL GROUP BY group_id ORDER BY group_id''')]
            self.cancel = threading.Event()
            self.groups = {g['group_id']: g for g in groups}
            self.pairs = []
            self.job = {'state': 'running', 'id': uuid.uuid4().hex, 'revision': revision,
                        'threshold': threshold, 'processed': 0, 'total': len(groups)*(len(groups)-1)//2}
            threading.Thread(target=self.run, args=(groups, self.cancel), daemon=True).start()
        return self.snapshot()

    def run(self, groups, cancel):
        try:
            prepared = [tokens(g['positive']) for g in groups]
            for i, left in enumerate(groups):
                for j in range(i+1, len(groups)):
                    if cancel.is_set():
                        with self.lock:
                            self.job['state'] = 'cancelled'
                        return
                    a, b = prepared[i], prepared[j]
                    bound = 200 * min(len(a), len(b)) / max(1, len(a)+len(b))
                    score = similarity(a, b) if bound >= self.job['threshold'] else -1
                    with self.lock:
                        if score >= self.job['threshold']:
                            self.pairs.append((score, left['group_id'], groups[j]['group_id']))
                        self.job['processed'] += 1
            with self.lock:
                self.pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
                self.job['state'] = 'cancelled' if cancel.is_set() else 'complete'
        except Exception as error:
            with self.lock:
                self.job.update(state='error', error=str(error))

    def snapshot(self, page=0):
        with self.lock:
            with self.library.connect() as db:
                revision = self.library.revision(db)
            result = dict(self.job)
            if result.get('revision', revision) != revision:
                self.cancel.set()
                result['state'] = 'stale'
            pairs = self.pairs if result['state'] == 'complete' else []
            result.update(matches=len(pairs), page=page, items=[])
            for score, a, b in pairs[page*20:(page+1)*20]:
                left, right = self.groups[a], self.groups[b]
                result['items'].append({'score': score, 'left': left, 'right': right,
                                        'differences': differences(left['positive'], right['positive'])})
            return result

    def prune(self, group, before, after):
        with self.lock:
            if self.job['state'] == 'complete' and self.job.get('revision') == before:
                self.pairs = [p for p in self.pairs if group not in p[1:]]
                self.job['revision'] = after
