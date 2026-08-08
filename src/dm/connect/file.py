"""文件连接器：CSV / Excel（接 MES 导出、线下台账）。

对标 Palantir 的 file-based sync。落地目录见 config.FILE_SOURCE_DIR（默认 DATA_DIR/file_sources）。
每个 .csv/.xlsx 文件 = 一个数据集；自省用 pandas 推断列类型。Excel 需 openpyxl（connectors extra）。
"""
from pathlib import Path
from typing import Optional

from dm.config import FILE_SOURCE_DIR
from dm.connect.base import ColumnDef, Connector, DatasetDef, Source

_EXTS = (".csv", ".xlsx", ".xls")
_EXT_PRIORITY = {ext: idx for idx, ext in enumerate(_EXTS)}


def default_file_source() -> Source:
    return Source(
        name="file_drop", source_type="file",
        params={"dir": str(FILE_SOURCE_DIR)},
        description="文件源（CSV/Excel，接 MES 导出/线下表）",
    )


def _dtype_to_base(dtype) -> str:
    s = str(dtype)
    if s.startswith("int"):
        return "integer"
    if s.startswith("float"):
        return "double"
    if s.startswith("datetime"):
        return "timestamp"
    if s == "bool":
        return "boolean"
    return "varchar"


class FileConnector(Connector):
    source_type = "file"

    def _dir(self) -> Path:
        return Path(self.source.params.get("dir", FILE_SOURCE_DIR))

    def _validated_dir(self) -> Path:
        d = self._dir()
        if not d.exists():
            raise FileNotFoundError(f"文件源目录不存在: {d}")
        if not d.is_dir():
            raise NotADirectoryError(f"文件源路径不是目录: {d}")
        return d

    @staticmethod
    def _validate_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("文件源数据集名称不能为空")
        if Path(name).name != name or "/" in name or "\\" in name or name in {".", ".."}:
            raise ValueError(f"文件源数据集名称只能是当前目录下的文件名或 stem: {name!r}")
        return name

    def _supported_files(self, d: Optional[Path] = None) -> list[Path]:
        d = d or self._validated_dir()
        return sorted(
            (p for p in d.iterdir() if p.is_file() and p.suffix.lower() in _EXTS),
            key=lambda p: (p.stem.casefold(), _EXT_PRIORITY[p.suffix.lower()], p.name.casefold()),
        )

    def _path(self, name: str) -> Path:
        d = self._validated_dir()
        name = self._validate_name(name)
        files = self._supported_files(d)

        # 允许调用方传完整文件名；Windows/macOS 导出的大小写后缀也能匹配。
        exact = next((p for p in files if p.name.casefold() == name.casefold()), None)
        if exact is not None:
            return exact

        # 常规 API 传 DatasetDef.name（stem）。同 stem 多格式时保持 CSV > XLSX > XLS 的优先级。
        by_stem = [p for p in files if p.stem.casefold() == name.casefold()]
        if by_stem:
            return min(by_stem, key=lambda p: _EXT_PRIORITY[p.suffix.lower()])

        raise FileNotFoundError(f"文件源未找到: {name}（目录 {d}）")

    def _read_df(self, path: Path, nrows: Optional[int] = None):
        import pandas as pd
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path, nrows=nrows)
        return pd.read_excel(path, nrows=nrows)

    def test_connection(self) -> tuple:
        d = self._dir()
        if not d.exists():
            return False, f"目录不存在: {d}"
        if not d.is_dir():
            return False, f"路径不是目录: {d}"
        return True, "ok"

    def introspect(self) -> list:
        d = self._dir()
        if not d.is_dir():
            return []
        out = []
        for p in self._supported_files(d):
            try:
                df = self._read_df(p, nrows=100)
            except Exception:  # noqa: BLE001
                continue
            cols = [ColumnDef(name=str(c), data_type=_dtype_to_base(df[c].dtype)) for c in df.columns]
            out.append(DatasetDef(name=p.stem, columns=cols))
        return out

    def read_table(self, name: str, limit: Optional[int] = None,
                   cursor_col: Optional[str] = None, since=None) -> tuple:
        df = self._read_df(self._path(name))
        if cursor_col and since is not None and cursor_col in df.columns:
            df = df[df[cursor_col] > since]
        if limit:
            df = df.head(int(limit))
        cols = [str(c) for c in df.columns]
        rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
        return cols, rows

    def capabilities(self) -> dict:
        return {"snapshot": True, "incremental": True, "cdc": False}
