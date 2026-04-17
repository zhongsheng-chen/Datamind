from pathlib import Path
from typing import Optional, List
from datamind.storage.base import StorageBackend


class LocalStorage(StorageBackend):

    def __init__(self, root: str = "./data"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key

    def save(self, key: str, data: bytes):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def load(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str):
        path = self._path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def list(self, prefix: Optional[str] = None) -> List[str]:
        base = self.root
        results = []

        for p in base.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(base))
                if prefix is None or rel.startswith(prefix):
                    results.append(rel)

        return results