"""Where project files live.

fs     : files under settings.workspace_root (the original behaviour, still the default).
db_s3  : text files in Postgres table workspace_files, binary files in the S3 bucket
         under workbench/<project>/<path>. Each row keeps sha256 and size.

Callers use get_store(); they do not pick a backend themselves.
"""

from __future__ import annotations

import fnmatch
import hashlib
import io
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Iterator, Protocol

from sqlalchemy import text

from src.core.config import settings

TEXT_EXT = {".md", ".txt", ".json", ".jsonl", ".csv", ".xml", ".yaml", ".yml"}
S3_PREFIX = "workbench/"

DDL = """
CREATE TABLE IF NOT EXISTS workspace_files (
    id          bigserial PRIMARY KEY,
    project_id  text NOT NULL,
    rel_path    text NOT NULL,
    storage     text NOT NULL CHECK (storage IN ('db', 's3')),
    content     text,
    s3_key      text,
    sha256      text NOT NULL,
    size_bytes  bigint NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, rel_path)
)
"""


def _clean_rel(rel: str) -> str:
    """Reject absolute paths, drive letters and '..' so a file cannot land outside its project."""
    p = PurePosixPath(rel.replace("\\", "/"))
    if not p.parts or p.is_absolute() or ":" in p.parts[0] or ".." in p.parts:
        raise ValueError(f"unsafe workspace path: {rel!r}")
    return p.as_posix()


class WorkspaceStore(Protocol):
    def read_bytes(self, project_id: str, rel: str) -> bytes | None: ...
    def write_bytes(self, project_id: str, rel: str, data: bytes) -> None: ...
    def exists(self, project_id: str, rel: str) -> bool: ...
    def list_files(self, project_id: str) -> list[str]: ...
    def delete(self, project_id: str, rel: str) -> None: ...
    def info(self, project_id: str, rel: str) -> tuple[int, float] | None: ...  # (size, mtime epoch)
    def projects(self) -> list[str]: ...


@dataclass
class StatResult:
    st_size: int
    st_mtime: float
    st_mtime_ns: int


class FsStore:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.workspace_root)

    def _path(self, project_id: str, rel: str) -> Path:
        return self.root / project_id / _clean_rel(rel)

    def read_bytes(self, project_id: str, rel: str) -> bytes | None:
        p = self._path(project_id, rel)
        return p.read_bytes() if p.is_file() else None

    def write_bytes(self, project_id: str, rel: str, data: bytes) -> None:
        p = self._path(project_id, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def exists(self, project_id: str, rel: str) -> bool:
        return self._path(project_id, rel).is_file()

    def info(self, project_id: str, rel: str) -> tuple[int, float] | None:
        p = self._path(project_id, rel)
        if not p.is_file():
            return None
        st = p.stat()
        return st.st_size, st.st_mtime

    def projects(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def list_files(self, project_id: str) -> list[str]:
        base = self.root / project_id
        if not base.is_dir():
            return []
        return sorted(f.relative_to(base).as_posix() for f in base.rglob("*") if f.is_file())

    def delete(self, project_id: str, rel: str) -> None:
        p = self._path(project_id, rel)
        if p.is_file():
            p.unlink()


class DbS3Store:
    """Postgres for text, S3 for binaries. Engine and S3 client can be injected for tests."""

    def __init__(self, engine=None, s3=None, bucket: str | None = None) -> None:
        self._engine = engine
        self._s3 = s3
        self._bucket = bucket or settings.s3_bucket
        self._ready = False

    @property
    def engine(self):
        if self._engine is None:
            from src.core.db.session import engine as app_engine

            self._engine = app_engine
        return self._engine

    @property
    def s3(self):
        if self._s3 is None:
            import urllib3
            from minio import Minio

            http = urllib3.PoolManager(cert_reqs="CERT_REQUIRED", ca_certs=settings.s3_ca_file or None)
            self._s3 = Minio(
                settings.s3_endpoint_url.replace("https://", "").replace("http://", ""),
                access_key=settings.s3_access_key_id,
                secret_key=settings.s3_secret_access_key,
                secure=settings.s3_endpoint_url.startswith("https://"),
                http_client=http,
            )
        return self._s3

    def _ensure(self) -> None:
        if not self._ready:
            with self.engine.begin() as conn:
                conn.exec_driver_sql(DDL)
            self._ready = True

    def _row(self, project_id: str, rel: str):
        with self.engine.connect() as conn:
            return conn.execute(
                text("select storage, content, s3_key from workspace_files "
                     "where project_id=:p and rel_path=:r"),
                {"p": project_id, "r": rel},
            ).first()

    def read_bytes(self, project_id: str, rel: str) -> bytes | None:
        self._ensure()
        rel = _clean_rel(rel)
        row = self._row(project_id, rel)
        if row is None:
            return None
        storage, content, key = row
        if storage == "db":
            return content.encode("utf-8")
        resp = self.s3.get_object(self._bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def write_bytes(self, project_id: str, rel: str, data: bytes) -> None:
        self._ensure()
        rel = _clean_rel(rel)
        sha = hashlib.sha256(data).hexdigest()
        as_text = None
        if Path(rel).suffix.lower() in TEXT_EXT:
            try:
                as_text = data.decode("utf-8")
            except UnicodeDecodeError:
                as_text = None
        old = self._row(project_id, rel)
        key = None
        if as_text is None:
            key = S3_PREFIX + f"{project_id}/{rel}"
            self.s3.put_object(self._bucket, key, io.BytesIO(data), len(data))
        with self.engine.begin() as conn:
            conn.execute(
                text("""insert into workspace_files
                        (project_id, rel_path, storage, content, s3_key, sha256, size_bytes, updated_at)
                        values (:p, :r, :st, :c, :k, :h, :n, now())
                        on conflict (project_id, rel_path) do update set
                          storage=excluded.storage, content=excluded.content, s3_key=excluded.s3_key,
                          sha256=excluded.sha256, size_bytes=excluded.size_bytes, updated_at=now()"""),
                {"p": project_id, "r": rel, "st": "db" if as_text is not None else "s3",
                 "c": as_text, "k": key, "h": sha, "n": len(data)},
            )
        # Old S3 object is only removed after the new row is saved.
        if old and old[0] == "s3" and old[2] != key:
            self.s3.remove_object(self._bucket, old[2])

    def exists(self, project_id: str, rel: str) -> bool:
        self._ensure()
        return self._row(project_id, _clean_rel(rel)) is not None

    def list_files(self, project_id: str) -> list[str]:
        self._ensure()
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("select rel_path from workspace_files where project_id=:p order by rel_path"),
                {"p": project_id},
            ).all()
        return [r[0] for r in rows]

    def projects(self) -> list[str]:
        self._ensure()
        with self.engine.connect() as conn:
            rows = conn.execute(text("select distinct project_id from workspace_files order by 1")).all()
        return [r[0] for r in rows]

    def info(self, project_id: str, rel: str) -> tuple[int, float] | None:
        self._ensure()
        with self.engine.connect() as conn:
            row = conn.execute(
                text("select size_bytes, extract(epoch from updated_at) from workspace_files "
                     "where project_id=:p and rel_path=:r"),
                {"p": project_id, "r": _clean_rel(rel)},
            ).first()
        return (int(row[0]), float(row[1])) if row else None

    def delete(self, project_id: str, rel: str) -> None:
        self._ensure()
        rel = _clean_rel(rel)
        row = self._row(project_id, rel)
        if row is None:
            return
        with self.engine.begin() as conn:
            conn.execute(text("delete from workspace_files where project_id=:p and rel_path=:r"),
                         {"p": project_id, "r": rel})
        if row[0] == "s3":
            self.s3.remove_object(self._bucket, row[2])


class WsPath:
    """A pathlib-like handle to a file or folder inside one project, backed by the store.

    Only the calls the app uses are implemented. Folders are implied by file keys, so
    mkdir() does nothing. Passing one to open() or a library that needs a real path fails
    on purpose: such code must use read_bytes()/write_bytes() instead.
    """

    __slots__ = ("store", "project_id", "rel")

    def __init__(self, store: WorkspaceStore, project_id: str, rel: str = "") -> None:
        self.store = store
        self.project_id = project_id
        self.rel = rel.replace("\\", "/").strip("/")

    def __repr__(self) -> str:
        return f"WsPath({self.project_id!r}, {self.rel!r})"

    def __str__(self) -> str:
        return f"{self.project_id}/{self.rel}" if self.rel else self.project_id

    def __eq__(self, other) -> bool:
        return isinstance(other, WsPath) and (self.project_id, self.rel) == (other.project_id, other.rel)

    def __hash__(self) -> int:
        return hash((self.project_id, self.rel))

    def __truediv__(self, other) -> "WsPath":
        part = str(other).replace("\\", "/").strip("/")
        return WsPath(self.store, self.project_id, f"{self.rel}/{part}" if self.rel else part)

    @property
    def name(self) -> str:
        return self.rel.rsplit("/", 1)[-1]

    @property
    def parts(self) -> tuple[str, ...]:
        return tuple(self.rel.split("/")) if self.rel else ()

    @property
    def suffix(self) -> str:
        return Path(self.name).suffix

    @property
    def stem(self) -> str:
        return Path(self.name).stem

    @property
    def parent(self) -> "WsPath":
        head = self.rel.rsplit("/", 1)[0] if "/" in self.rel else ""
        return WsPath(self.store, self.project_id, head)

    @property
    def parents(self) -> list["WsPath"]:
        out: list[WsPath] = []
        cur = self.parent if self.rel else None
        while cur is not None:
            out.append(cur)
            cur = cur.parent if cur.rel else None
        return out

    def resolve(self, strict: bool = False) -> "WsPath":
        return self  # no symlinks in the store; the path is already normalised

    def as_posix(self) -> str:
        return self.rel

    def relative_to(self, other: "WsPath") -> "WsPath":
        if not isinstance(other, WsPath) or other.project_id != self.project_id:
            raise ValueError(f"{self} is not under {other}")
        if not other.rel:
            return WsPath(self.store, self.project_id, self.rel)
        if self.rel == other.rel or not self.rel.startswith(other.rel + "/"):
            raise ValueError(f"{self} is not under {other}")
        return WsPath(self.store, self.project_id, self.rel[len(other.rel) + 1:])

    def with_suffix(self, suffix: str) -> "WsPath":
        head = self.rel[: -len(self.suffix)] if self.suffix else self.rel
        return WsPath(self.store, self.project_id, head + suffix)

    def with_name(self, name: str) -> "WsPath":
        head = self.rel.rsplit("/", 1)[0] if "/" in self.rel else ""
        return WsPath(self.store, self.project_id, f"{head}/{name}" if head else name)

    def with_stem(self, stem: str) -> "WsPath":
        return self.with_name(stem + self.suffix)

    def _all(self) -> list[str]:
        return self.store.list_files(self.project_id)

    def is_file(self) -> bool:
        return bool(self.rel) and self.store.exists(self.project_id, self.rel)

    def is_dir(self) -> bool:
        if not self.rel:
            return True
        prefix = self.rel + "/"
        return any(f.startswith(prefix) for f in self._all())

    def exists(self) -> bool:
        return self.is_file() or self.is_dir()

    def stat(self) -> StatResult:
        found = self.store.info(self.project_id, self.rel)
        if found is None:
            raise FileNotFoundError(str(self))
        size, mtime = found
        return StatResult(st_size=size, st_mtime=mtime, st_mtime_ns=int(mtime * 1_000_000_000))

    def read_bytes(self) -> bytes:
        data = self.store.read_bytes(self.project_id, self.rel)
        if data is None:
            raise FileNotFoundError(str(self))
        return data

    def read_text(self, encoding: str = "utf-8", errors: str = "strict") -> str:
        return self.read_bytes().decode(encoding, errors)

    def write_bytes(self, data: bytes) -> int:
        self.store.write_bytes(self.project_id, self.rel, bytes(data))
        return len(data)

    def write_text(self, data: str, encoding: str = "utf-8", errors: str | None = None) -> int:
        self.write_bytes(data.encode(encoding, errors or "strict"))
        return len(data)

    def open(self, mode: str = "r", encoding: str | None = None, errors: str | None = None, newline=None):
        """Read ('r', 'rb') or write/append ('w', 'wb', 'a', 'ab'). Writes are saved when the block ends."""
        enc = encoding or "utf-8"
        if "r" in mode:
            data = self.read_bytes()
            if "b" in mode:
                return io.BytesIO(data)
            return io.StringIO(data.decode(enc, errors or "strict"))
        initial = self.read_bytes() if ("a" in mode and self.is_file()) else b""
        return _WriteBack(self, initial, binary="b" in mode, encoding=enc, errors=errors or "strict")

    def mkdir(self, parents: bool = False, exist_ok: bool = False) -> None:
        return None  # folders are implied by the files stored under them

    def rmtree(self, ignore_errors: bool = False) -> None:
        prefix = self.rel + "/" if self.rel else ""
        for f in self._all():
            if f.startswith(prefix):
                self.store.delete(self.project_id, f)

    def unlink(self, missing_ok: bool = False) -> None:
        if not self.is_file():
            if missing_ok:
                return
            raise FileNotFoundError(str(self))
        self.store.delete(self.project_id, self.rel)

    def iterdir(self):
        prefix = self.rel + "/" if self.rel else ""
        seen: set[str] = set()
        for f in self._all():
            if not f.startswith(prefix):
                continue
            child = f[len(prefix):].split("/", 1)[0]
            if child not in seen:
                seen.add(child)
                yield WsPath(self.store, self.project_id, prefix + child)

    def glob(self, pattern: str):
        """Direct children matching pattern (pathlib semantics, no recursion)."""
        prefix = self.rel + "/" if self.rel else ""
        for f in self._all():
            if f.startswith(prefix) and "/" not in f[len(prefix):] and fnmatch.fnmatch(f[len(prefix):], pattern):
                yield WsPath(self.store, self.project_id, f)

    def rglob(self, pattern: str):
        """All files below this folder whose name matches pattern (a leading '**/' is allowed)."""
        prefix = self.rel + "/" if self.rel else ""
        name_pat = pattern[3:] if pattern.startswith("**/") else pattern
        for f in self._all():
            if f.startswith(prefix) and fnmatch.fnmatch(f.rsplit("/", 1)[-1], name_pat):
                yield WsPath(self.store, self.project_id, f)


class _WriteBack:
    """Buffers writes and saves the whole file to the store on close."""

    def __init__(self, path: WsPath, initial: bytes, binary: bool, encoding: str, errors: str) -> None:
        self._path = path
        self._binary = binary
        self._enc = encoding
        self._err = errors
        self._buf = io.BytesIO(initial)
        self._buf.seek(0, io.SEEK_END)
        self._closed = False

    def write(self, data) -> int:
        if self._binary:
            return self._buf.write(bytes(data))
        raw = data.encode(self._enc, self._err)
        self._buf.write(raw)
        return len(data)

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._path.write_bytes(self._buf.getvalue())
            self._buf.close()


def as_path(value):
    """Use Path(...) only for strings; a Path or WsPath is returned unchanged."""
    return value if isinstance(value, (Path, WsPath)) else Path(value)


def download_response(path, media_type: str | None = None, filename: str | None = None):
    """FileResponse for a real file; a bytes response for a file kept in the store."""
    from urllib.parse import quote

    from fastapi.responses import FileResponse, Response

    if isinstance(path, WsPath):
        headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename or path.name)}"}
        return Response(content=path.read_bytes(), media_type=media_type or "application/octet-stream",
                        headers=headers)
    return FileResponse(path=str(path), media_type=media_type, filename=filename)


def remove_tree(path, ignore_errors: bool = True) -> None:
    """shutil.rmtree for both real folders and store-backed folders."""
    if isinstance(path, WsPath):
        path.rmtree(ignore_errors=ignore_errors)
    else:
        shutil.rmtree(path, ignore_errors=ignore_errors)


def project_root(project_id: str):
    """Real folder in fs mode, WsPath in db_s3 mode."""
    if settings.workspace_backend == "db_s3":
        return WsPath(get_store(), project_id)
    return Path(settings.workspace_root) / project_id


@contextmanager
def scratch(project_id: str, rel: str = "", hydrate: bool = False) -> Iterator[Path]:
    """A real local folder for code that needs one (renderers, Excel/Word writers, tools).

    fs mode: yields the project folder itself (no copying).
    db_s3 mode: yields a temporary folder under the system temp dir. If hydrate is True, the
    stored files under rel are copied in first. On exit every new or changed file is written
    to the store and the temporary folder is deleted.
    """
    if settings.workspace_backend != "db_s3":
        target = Path(settings.workspace_root) / project_id / rel
        target.mkdir(parents=True, exist_ok=True)
        yield target
        return

    store = get_store()
    tmp = Path(tempfile.mkdtemp(prefix="aw_scratch_"))
    prefix = rel.strip("/") + "/" if rel else ""
    try:
        before: dict[str, str] = {}
        if hydrate:
            for f in store.list_files(project_id):
                if f.startswith(prefix):
                    data = store.read_bytes(project_id, f) or b""
                    local = tmp / f[len(prefix):]
                    local.parent.mkdir(parents=True, exist_ok=True)
                    local.write_bytes(data)
                    before[f] = hashlib.sha256(data).hexdigest()
        yield tmp
        for path in sorted(p for p in tmp.rglob("*") if p.is_file()):
            rel_child = path.relative_to(tmp).as_posix()
            data = path.read_bytes()
            key = prefix + rel_child
            if before.get(key) == hashlib.sha256(data).hexdigest():
                continue
            store.write_bytes(project_id, key, data)
        if hydrate:
            # Files that existed before but were deleted during the block are removed from the store.
            for key in before:
                if not (tmp / key[len(prefix):]).is_file():
                    store.delete(project_id, key)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def list_projects() -> list[str]:
    """Every project that has files in the active store."""
    return get_store().projects()


@lru_cache(maxsize=1)
def get_store() -> WorkspaceStore:
    if settings.workspace_backend == "db_s3":
        return DbS3Store()
    if settings.workspace_backend != "fs":
        raise ValueError(f"WORKSPACE_BACKEND must be fs or db_s3, got {settings.workspace_backend!r}")
    return FsStore()
