"""文件连接器：CSV / Excel（接 MES 导出、线下台账）。"""
from os import PathLike
from pathlib import Path
from typing import Optional

from dm.config import FILE_SOURCE_DIR
from dm.connect.base import ColumnDef, Connector, DatasetDef, Source, normalize_read_limit

_EXTS = (".csv", ".xlsx", ".xls")
_EXT_PRIORITY = {ext: idx for idx, ext in enumerate(_EXTS)}


def default_file_source() -> Source:
    return Source(name="file_drop", source_type="file", params={"dir": str(FILE_SOURCE_DIR)}, description="文件源（CSV/Excel，接 MES 导出/线下表）")


def _dtype_to_base(dtype) -> str:
    s = str(dtype).lower()
    if s.startswith(("int", "uint")): return "integer"
    if s.startswith("float"): return "double"
    if s.startswith("datetime"): return "timestamp"
    if s in {"bool", "boolean"}: return "boolean"
    return "varchar"


class FileConnector(Connector):
    source_type = "file"

    def _dir(self) -> Path:
        raw = self.source.params.get("dir", FILE_SOURCE_DIR)
        if not isinstance(raw, (str, PathLike)):
            raise ValueError(f"文件源目录必须是路径字符串: {raw!r}")
        if isinstance(raw, str) and not raw.strip():
            raise ValueError("文件源目录不能为空")
        return Path(raw)

    def _validated_dir(self) -> Path:
        d = self._dir()
        if not d.exists(): raise FileNotFoundError(f"文件源目录不存在: {d}")
        if not d.is_dir(): raise NotADirectoryError(f"文件源路径不是目录: {d}")
        return d

    @staticmethod
    def _validate_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip(): raise ValueError("文件源数据集名称不能为空")
        if name != name.strip(): raise ValueError(f"文件源数据集名称不能包含首尾空白: {name!r}")
        if Path(name).name != name or "/" in name or "\\" in name or name in {".", ".."}: raise ValueError(f"文件源数据集名称只能是当前目录下的文件名或 stem: {name!r}")
        return name

    def _supported_files(self, d: Optional[Path] = None) -> list[Path]:
        d = d or self._validated_dir()
        return sorted((p for p in d.iterdir() if p.is_file() and p.suffix.lower() in _EXTS), key=lambda p: (p.stem.casefold(), _EXT_PRIORITY[p.suffix.lower()], p.name.casefold(), p.name))

    def _logical_files(self, d: Optional[Path] = None) -> list[Path]:
        groups: dict[str, list[Path]] = {}
        for p in self._supported_files(d):
            groups.setdefault(p.stem.casefold(), []).append(p)
        chosen = []
        for group in groups.values():
            best_priority = min(_EXT_PRIORITY[p.suffix.lower()] for p in group)
            preferred = [p for p in group if _EXT_PRIORITY[p.suffix.lower()] == best_priority]
            if len(preferred) > 1:
                names = ", ".join(sorted(p.name for p in preferred))
                raise ValueError(f"文件源 stem 存在仅大小写不同的歧义: {preferred[0].stem!r} -> {names}")
            chosen.append(preferred[0])
        return chosen

    @staticmethod
    def _single_casefold_match(paths: list[Path], requested: str, attr: str) -> Optional[Path]:
        folded = requested.casefold()
        matches = [p for p in paths if getattr(p, attr).casefold() == folded]
        if len(matches) > 1:
            names = ", ".join(sorted(p.name for p in matches))
            raise ValueError(f"文件源名称存在仅大小写不同的歧义: {requested!r} -> {names}")
        return matches[0] if matches else None

    def _path(self, name: str) -> Path:
        d = self._validated_dir(); name = self._validate_name(name); files = self._supported_files(d)
        literal = next((p for p in files if p.name == name), None)
        if literal is not None: return literal
        exact = self._single_casefold_match(files, name, "name")
        if exact is not None: return exact
        by_stem = [p for p in files if p.stem.casefold() == name.casefold()]
        if by_stem:
            best_priority = min(_EXT_PRIORITY[p.suffix.lower()] for p in by_stem)
            preferred = [p for p in by_stem if _EXT_PRIORITY[p.suffix.lower()] == best_priority]
            if len(preferred) > 1:
                names = ", ".join(sorted(p.name for p in preferred))
                raise ValueError(f"文件源 stem 存在仅大小写不同的歧义: {name!r} -> {names}")
            return preferred[0]
        raise FileNotFoundError(f"文件源未找到: {name}（目录 {d}）")

    def _read_df(self, path: Path, nrows: Optional[int] = None):
        import pandas as pd
        if path.suffix.lower() == ".csv": return pd.read_csv(path, nrows=nrows)
        return pd.read_excel(path, nrows=nrows)

    def test_connection(self) -> tuple:
        try:
            d = self._dir()
        except ValueError as exc:
            return False, str(exc)
        if not d.exists(): return False, f"目录不存在: {d}"
        if not d.is_dir(): return False, f"路径不是目录: {d}"
        return True, "ok"

    def introspect(self) -> list:
        d = self._validated_dir()
        out = []
        for p in self._logical_files(d):
            try: df = self._read_df(p, nrows=100)
            except Exception: continue  # noqa: BLE001
            cols = [ColumnDef(name=str(c), data_type=_dtype_to_base(df[c].dtype)) for c in df.columns]
            out.append(DatasetDef(name=p.stem, columns=cols))
        return out

    def read_table(self, name: str, limit: Optional[int] = None, cursor_col: Optional[str] = None, since=None) -> tuple:
        limit = normalize_read_limit(limit); incremental = since is not None
        if cursor_col is not None and since is None: raise ValueError("增量读取提供 cursor_col 时必须同时提供 since")
        if incremental and (not isinstance(cursor_col, str) or not cursor_col.strip()): raise ValueError("增量读取提供 since 时必须同时提供非空 cursor_col")
        df = self._read_df(self._path(name), nrows=None if incremental else limit)
        if incremental:
            if cursor_col not in df.columns: raise ValueError(f"增量游标列不存在: {cursor_col}")
            df = df[df[cursor_col] > since]
            if limit is not None: df = df.head(limit)
        cols = [str(c) for c in df.columns]; rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
        return cols, rows

    def capabilities(self) -> dict:
        return {"snapshot": True, "incremental": True, "cdc": False}
