#!/usr/bin/env python3
"""开源敏感词审计：扫描 git 跟踪的文本文件，命中即失败（exit 1）。

三用：迁移后本地把关 / CI 守门（.github/workflows/ci.yml 的 audit job）/ 推送后生成移交报告。

用法：
  python scripts/audit_sensitive.py                # 控制台输出，命中则 exit 1
  python scripts/audit_sensitive.py --report audit-report.md   # 另存 markdown 报告
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

# 零容忍模式（大小写不敏感）：命中任何一条即审计失败。
# 这些是历史客户/站点专属标识，公开仓库中的合法出现次数 = 0。
FORBIDDEN = [
    r"demate",                    # 历史客户品牌（含 db 名/密码/镜像名等一切变体）
    r"德玛特",
    r"佛山",
    r"8\.163\.250\.\d+",          # 历史站点公网 IP 段
    r"192\.168\.0\.\d+",          # 历史站点内网 IP
    r"aliyun_demate",             # 历史 SSH 私钥名
    r"海漫思",                     # 相关厂商真名
    r"超聚变|FusionXpark",         # 站点硬件品牌型号
    r"Leonxu6/datamanagement",    # 私有仓库路径
    r"qwable",                    # 私有网关模型别名
    r"om-root-2026|DemateU8|demate-kg",  # 品牌化历史口令
]

TEXT_EXT_SKIP = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".jar", ".pyc"}


def tracked_files(root: Path) -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    return [root / p for p in out.splitlines() if p and (root / p).suffix.lower() not in TEXT_EXT_SKIP]


def scan(root: Path) -> list[tuple[str, int, str, str]]:
    """返回 [(相对路径, 行号, 模式, 行内容截断)]。"""
    pats = [(p, re.compile(p, re.IGNORECASE)) for p in FORBIDDEN]
    hits = []
    me = Path(__file__).resolve()
    for f in tracked_files(root):
        if f.resolve() == me:      # 本脚本自身携带模式清单，豁免
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", help="另存 markdown 报告的路径")
    args = ap.parse_args()

    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                               text=True, encoding="utf-8", check=True).stdout.strip())
    hits = scan(root)

    lines = [f"# 敏感词审计报告", "",
             f"- 扫描根：`{root}`",
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
