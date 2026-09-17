from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_sensitive.py"
spec = spec_from_file_location("audit_sensitive", MODULE_PATH)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_tracked_files_preserves_newlines_in_git_paths(monkeypatch, tmp_path):
    result = SimpleNamespace(stdout="README.md\0docs/odd\nname.md\0image.png\0")

    def fake_run(*args, **kwargs):
        assert args[0] == ["git", "ls-files", "-z"]
        assert kwargs["cwd"] == tmp_path
        return result

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.tracked_files(tmp_path) == [
        tmp_path / "README.md",
        tmp_path / "docs" / "odd\nname.md",
    ]
