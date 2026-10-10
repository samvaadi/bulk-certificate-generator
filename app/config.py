from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'certificates.db').as_posix()}")
CERTIFICATE_STORAGE_DIR = Path(os.getenv("CERTIFICATE_STORAGE_DIR", str(BASE_DIR / "storage" / "certificates")))
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "certificate.html"
