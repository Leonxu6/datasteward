"""FileConnector must not escape its configured drop directory."""

from pathlib import Path

from dm.connect.base import Source
from dm.connect.file import FileConnector


def _connector(path: Path) -> FileConnector:
    return FileConnector(
        Source(name="files", source_type="file", params={"dir": str(path)})
    )


def test_file_connector_ignores_symlinks_to_external_files(tmp_path: Path):
    source_dir = tmp_path / "drop"
    source_dir.mkdir()
    external = tmp_path / "external.csv"
    external.write_text("id\n99\n", encoding="utf-8")
    (source_dir / "external.csv").symlink_to(external)
    (source_dir / "local.csv").write_text("id\n1\n", encoding="utf-8")

    datasets = _connector(source_dir).introspect()

    assert [dataset.name for dataset in datasets] == ["local"]
