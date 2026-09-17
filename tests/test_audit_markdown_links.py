from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_markdown_links.py"
spec = spec_from_file_location("audit_markdown_links", MODULE_PATH)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_checker_accepts_existing_local_and_external_links(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "other.md").write_text("# Other\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[local](docs/other.md) [web](https://example.com)\n", encoding="utf-8")
    assert module.broken_local_links(tmp_path) == []


def test_checker_accepts_query_fragments_and_external_url_forms(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "other.md").write_text("# Other\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[query](docs/other.md?raw=1#section) "
        "[upper](HTTPS://example.com/path) "
        "[protocol-relative](//example.com/path) "
        "[mail](MAILTO:maintainer@example.com)\n",
        encoding="utf-8",
    )

    assert module.broken_local_links(tmp_path) == []


def test_checker_reports_missing_local_target_and_preserves_anchor(tmp_path):
    (tmp_path / "README.md").write_text("[missing](docs/nope.md#section)\n", encoding="utf-8")
    assert module.broken_local_links(tmp_path) == [(Path("README.md"), "docs/nope.md#section")]


def test_checker_rejects_local_links_that_escape_repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (tmp_path / "outside.md").write_text("# Outside\n", encoding="utf-8")
    (root / "README.md").write_text("[escape](../outside.md)\n", encoding="utf-8")

    assert module.broken_local_links(root) == [(Path("README.md"), "../outside.md")]


def test_checker_does_not_follow_markdown_source_symlinks(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    external = tmp_path / "external.md"
    external.write_text("[missing](not-in-repo.md)\n", encoding="utf-8")
    (root / "linked.md").symlink_to(external)

    assert module.broken_local_links(root) == []
