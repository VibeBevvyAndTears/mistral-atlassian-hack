"""Local filesystem storage for tests/dev (persists blobs so ingest can parse)."""

from __future__ import annotations

from pathlib import Path

from src.lib.storage.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    """Writes blobs under a local root so download works for ingest parsing."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.cwd() / ".data" / "storage"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, bucket: str, key: str) -> Path:
        safe = key.lstrip("/").replace("..", "_")
        path = self.root / bucket / safe
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def upload(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> str:
        del content_type
        path = self._path(bucket, key)
        path.write_bytes(data)
        return f"local://{bucket}/{key}"

    async def download(self, bucket: str, key: str) -> bytes:
        path = self._path(bucket, key)
        if not path.is_file():
            raise FileNotFoundError(f"local blob missing: {bucket}/{key}")
        return path.read_bytes()

    async def delete(self, bucket: str, key: str) -> None:
        path = self._path(bucket, key)
        if path.is_file():
            path.unlink()

    async def get_signed_url(
        self, bucket: str, key: str, expires_in: int = 3600
    ) -> str:
        del expires_in
        return f"local://{bucket}/{key}"
