"""Backup, restore, dan tulis atomik. File asli tidak pernah ditimpa tanpa konfirmasi eksplisit."""
from __future__ import annotations
import json, os, shutil, tempfile, time, hashlib
from pathlib import Path

def sha256_of(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(1 << 20): h.update(b)
    return h.hexdigest()

def atomic_write(dest, data: bytes):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=".tmp_", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, dest)
    except BaseException:
        if os.path.exists(tmp): os.unlink(tmp)
        raise

class BackupManager:
    def __init__(self, backup_dir):
        self.dir = Path(backup_dir); self.dir.mkdir(parents=True, exist_ok=True)

    def create(self, src) -> Path:
        src = Path(src)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        dst = self.dir / f"{src.name}.{stamp}.bak"
        n = 1
        while dst.exists():
            dst = self.dir / f"{src.name}.{stamp}_{n}.bak"; n += 1
        shutil.copy2(src, dst)
        meta = {"source": str(src), "sha256": sha256_of(dst), "size": dst.stat().st_size, "created": stamp}
        Path(str(dst) + ".json").write_text(json.dumps(meta, indent=2))
        return dst

    def list(self):
        return sorted(self.dir.glob("*.bak"))

    def verify(self, bak) -> bool:
        meta = json.loads(Path(str(bak) + ".json").read_text())
        return sha256_of(bak) == meta["sha256"]

    def restore(self, bak, dest, overwrite=False) -> Path:
        """Restore ke `dest`. Menimpa file yang ada hanya jika overwrite=True."""
        bak, dest = Path(bak), Path(dest)
        if not self.verify(bak):
            raise ValueError("Backup rusak: hash tidak cocok. Restore dibatalkan.")
        if dest.exists() and not overwrite:
            raise FileExistsError(f"{dest} sudah ada; setel overwrite=True untuk menimpa.")
        atomic_write(dest, bak.read_bytes())
        return dest
