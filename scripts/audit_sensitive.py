#!/usr/bin/env python3
"""开源敏感词审计：扫描 git 跟踪的文本文件，命中即失败（exit 1）。

三用：迁移后本地把关 / CI 守门 / 推送后生成移交报告。

用法：
  python scripts/audit_sensitive.py
  python scripts/audit_sensitive.py .
  python scripts/audit_sensitive.py --report audit-report.md
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN = [
    r"demate", r"德玛特", r"佛山", r"8\.163\.250\.\d+", r"192\.168\.0\.\d+",
    r"aliyun_demate", r"海漫思", r"超聚变|FusionXpark", r"Leonxu6/datamanagement",
    r"qwable", r"om-root-2026|DemateU8|demate-kg",
]
TEXT_EXT_SKIP = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".jar", ".pyc"}
_GIT_TIMEOUT = 10


def tracked_files(root: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True,
        encoding="utf-8", check=True, timeout=_GIT_TIMEOUT,
    ).stdout
    return [root / p for p in out.splitlines() if p and (root / p).suffix.lower() not in TEXT_EXT_SKIP]


def scan(root: Path) -> list[tuple[str, int, str, str]]:
    pats = [(p, re.compile(p, re.IGNORECASE)) for p in FORBIDDEN]
    hits = []
    me = Path(__file__).resolve()
    for f in tracked_files(root):
        if f.resolve() == me:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for ln, line in enumerate(text.splitlines(), 1):
            for raw, rx in pats:
                if rx.search(line):
                    hits.append((str(f.relative_to(root)), ln, raw, line.strip()[:120]))
    return hits


def _repository_root(value: str | None) -> Path:
    if value is not None:
        root = Path(value).expanduser().resolve()
        if not root.is_dir():
            raise ValueError("repository root must be an existing directory")
        return root
    return Path(subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True,
        text=True, encoding="utf-8", check=True, timeout=_GIT_TIMEOUT,
    ).stdout.strip())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", help="repository root (defaults to current Git worktree)")
    ap.add_argument("--report", help="另存 markdown 报告的路径")
    args = ap.parse_args(argv)
    try:
        root = _repository_root(args.root)
    except (ValueError, subprocess.SubprocessError) as exc:
        ap.error(str(exc))

    hits = scan(root)
    lines = ["# 敏感词审计报告", "", f"- 扫描根：`{root}`",
             f"- 模式数：{len(FORBIDDEN)}（大小写不敏感，零容忍）",
             f"- 结果：**{'❌ ' + str(len(hits)) + ' 处命中' if hits else '✅ 零命中'}**", ""]
    if hits:
        lines += ["| 文件 | 行 | 模式 | 内容 |", "|---|---|---|---|"]
        lines += [f"| {f} | {ln} | `{p}` | `{t}` |" for f, ln, p, t in hits]
    report = "\n".join(lines)
    print(report)
    if args.report:
        Path(args.report).write_text(report + "\n", encoding="utf-8")
        print(f"\n报告已写入 {args.report}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
