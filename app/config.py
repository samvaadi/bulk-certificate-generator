from pathlib import Path
import os
from slowapi import Limiter
from slowapi.util import get_remote_address

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'certificates.db').as_posix()}")
CERTIFICATE_STORAGE_DIR = Path(os.getenv("CERTIFICATE_STORAGE_DIR", str(BASE_DIR / "storage" / "certificates")))
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "certificate.html"
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
if MAX_WORKERS < 1:
    raise ValueError("MAX_WORKERS must be at least 1")
limiter = Limiter(key_func=get_remote_address, default_limits=[])
