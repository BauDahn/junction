import hashlib
import json
from pathlib import Path


class DiskCache:
    def __init__(self, root):
        self.root = Path(root)

    def key(self, value):
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, namespace, value):
        path = self.root / namespace / f"{self.key(value)}.json"
        return json.loads(path.read_text()) if path.exists() else None

    def put(self, namespace, value, result):
        path = self.root / namespace / f"{self.key(value)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
