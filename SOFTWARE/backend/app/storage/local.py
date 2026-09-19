from __future__ import annotations

from pathlib import Path


class LocalFilesystemStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        relative = Path(key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Neispravan ključ skladišta")
        path = (self.root / relative).resolve()
        if not str(path).startswith(str(self.root)):
            raise ValueError("Neispravan ključ skladišta")
        return path

    def put(self, key: str, content: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def local_path(self, key: str) -> Path | None:
        return self._path(key)
