from pathlib import Path
from tempfile import TemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile
from app.config import CERTIFICATE_STORAGE_DIR


class StorageService:
    @staticmethod
    def save(job_id: str, recipient_id: str, data: bytes) -> Path:
        directory = CERTIFICATE_STORAGE_DIR / job_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{recipient_id}.pdf"
        target.write_bytes(data)
        return target

    @staticmethod
    def existing_path(path: str) -> Path | None:
        candidate = Path(path).resolve()
        root = CERTIFICATE_STORAGE_DIR.resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            return None
        return candidate

    @staticmethod
    def iter_zip(paths: list[str], chunk_size: int = 64 * 1024):
        """Yield a ZIP in bounded chunks; only the current file is read at once."""
        with TemporaryFile(mode="w+b") as buffer:
            with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
                for raw_path in paths:
                    path = StorageService.existing_path(raw_path)
                    if path is None:
                        continue
                    with path.open("rb") as source, archive.open(path.name, "w") as destination:
                        while chunk := source.read(chunk_size):
                            destination.write(chunk)
            buffer.seek(0)
            while chunk := buffer.read(chunk_size):
                yield chunk
