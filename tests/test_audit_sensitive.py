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


def test_scan_does_not_follow_tracked_symlink_contents(monkeypatch, tmp_path):
    external = tmp_path / "external.md"
    external.write_text("demate should not be read through the link\n", encoding="utf-8")
    link = tmp_path / "linked.md"
    link.symlink_to(external)
    monkeypatch.setattr(module, "tracked_files", lambda _root: [link])

    assert module.scan(tmp_path) == []


def test_scan_still_checks_the_tracked_symlink_target_text(monkeypatch, tmp_path):
    link = tmp_path / "linked.md"
    link.symlink_to("demate-target")
    monkeypatch.setattr(module, "tracked_files", lambda _root: [link])

    hits = module.scan(tmp_path)

    assert len(hits) == 1
    assert hits[0][0] == "linked.md"
    assert hits[0][2] == "demate"
