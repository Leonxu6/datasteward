# Contributing to DataSteward

[English](#english) | [中文](#中文)

## 中文

### 开发环境

```bash
git clone https://github.com/Leonxu6/datasteward && cd datasteward
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .[dev,rag,kg,agent,connectors,dbt,orchestration,dingtalk]
```

### 两档测试

| 档位 | 命令 | 需要什么 |
|---|---|---|
| 纯单元（默认） | `pytest -m "not integration and not stack"` | 什么都不需要，裸机即跑 |
| stack 用例 | `docker compose -f deploy/docker-compose.yml up -d` 后 `pytest -m "stack and not integration"` | StarRocks/Postgres 栈 |

- `stack` 用例在栈不可达时**自动跳过**（不会报错），直接 `pytest` 也安全。
- `integration` 用例需要真实 LLM 端点，本地按需跑。
- CI（GitHub Actions）跑：单元子集 + `dbt parse` + `docker compose config` + 仓库维护审计。
- 本地可单独执行 `python -m scripts.run_maintenance_audits`，在 push 前复现 CI 的仓库维护门禁。

### 仓库维护审计

维护审计不仅检查敏感信息，也检查配置/文档语法、供应链和常见危险代码模式。JSON/TOML/YAML 语法审计会拒绝符号链接和伪装成配置文件的目录，避免审计器跨出仓库读取其他文件；JSON 还拒绝重复 object key 与 `NaN`/`Infinity` 等非标准常量；YAML 使用 safe loader，拒绝字面重复 mapping key，同时保留 Docker Compose `<<:` anchor 等标准 merge-key override 语义。

为了让 CI 的资源成本保持可预测，单个被跟踪的 JSON 文件上限为 **4 MiB**，TOML 与 YAML 文件上限均为 **2 MiB**。此外，参与运行时代码 AST 审计的 Python 源文件单文件上限为 **1 MiB**，这样意外提交的生成文件或损坏源码不会让几十项静态规则反复无界读取同一大文件。超过上限时审计会明确失败，而不是把整个超大文件读入内存继续解析。如果确实需要提交更大的机器生成数据，请不要把它伪装成运行配置或运行时代码，优先放到合适的 artifact/data 流程中。

### Windows 注意事项

- 跑 dbt 前设 `PYTHONUTF8=1`（中文注释在 GBK locale 下会炸，见 docs/DEVLOG.md 坑21）。
- `deploy/quickstart.sh` 请在 Git Bash 或 WSL 里跑（需 Docker Desktop + WSL2 后端）。

### 数据与测试须知

- **`src/dm/schema.py` 是单一真相源**：19 表模型驱动建表 DDL、CDC SQL 生成、造数、MCP 自省——改表结构只改这里。改 CDC 口径要改 `src/dm/pipeline/gen_flink_cdc_sql.py` 后重新生成 `infra/cdc_*.sql`，不要手改 SQL。
- **稳定测试 ID（冻结契约）**：`M0001`（总库存 12 @ `W02`）、`SO0001`（需 `M0046`×265）、`S001`（PO `PO0021`）——冒烟、eval 真值、README 演示都依赖它们。
- **`TODAY = date(2026, 6, 25)`**（`dm/warehouse/generate.py`，`dm/ontology/actions.py` 有同值副本）刻意固定为数据锚，eval SQL 真值依赖它，**勿改成 `date.today()`**；dbt 侧同值 `anchor_today`，模型里严禁 `current_date`。
- **调试套路**：Streamlit 治理台按 `session_id` 回放任务链 → 定位失败步骤（错表/错 SQL/幻觉）→ 修复——它是调试工具，不只是展示界面。

### PR 规范

- **一个 PR 只做一件事**，不堆叠无关改动。
- Commit message 中文或英文皆可，讲清"改了什么 + 为什么"。
- 行为变化需要配套测试；新功能优先补 eval 用例（`src/dm/eval/eval_set.yaml`）。
- 踩到新的技术坑，请把"现象 + 根因 + 解法"追加到 `docs/DEVLOG.md`。

### 文档语言

深度文档（docs/）目前以中文为主，英文翻译欢迎 PR。README 保持中英双语同步。

---

## English

### Dev setup

```bash
git clone https://github.com/Leonxu6/datasteward && cd datasteward
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .[dev,rag,kg,agent,connectors,dbt,orchestration,dingtalk]
```

### Two tiers of tests

| Tier | Command | Requires |
|---|---|---|
| Unit (default) | `pytest -m "not integration and not stack"` | Nothing — runs on a bare machine |
| Stack tests | `docker compose -f deploy/docker-compose.yml up -d`, then `pytest -m "stack and not integration"` | StarRocks/Postgres stack |

- `stack` tests **auto-skip** when the stack is unreachable, so a plain `pytest` is always safe.
- `integration` tests need a real LLM endpoint; run locally as needed.
- CI runs: unit subset + `dbt parse` + `docker compose config` + repository maintenance audits.
- Run `python -m scripts.run_maintenance_audits` locally to reproduce the repository-maintenance gate before pushing.

### Repository maintenance audits

Maintenance checks cover more than secret scanning: they also validate configuration/document syntax, supply-chain contracts, and common dangerous code patterns. JSON/TOML/YAML syntax audits reject symbolic links and directories masquerading as configuration files so the checker does not follow repository paths into unrelated files. JSON additionally rejects duplicate object keys and non-standard constants such as `NaN` and `Infinity`; YAML uses a safe loader, rejects literal duplicate mapping keys, and preserves standard merge-key overrides such as Docker Compose `<<:` anchors.

To keep CI resource usage predictable, each tracked JSON file is limited to **4 MiB**, while tracked TOML and YAML files are each limited to **2 MiB**. Runtime Python files consumed by the AST maintenance suite are additionally capped at **1 MiB per source file**, preventing an accidentally committed generated or corrupted module from being reread without bound by dozens of static rules. Oversized files fail with an explicit audit error instead of being read and parsed without a bound. If a larger generated payload is genuinely required, keep it in an appropriate artifact/data path rather than disguising it as runtime configuration or runtime source code.

### Windows notes

- Set `PYTHONUTF8=1` before running dbt (Chinese comments crash under the GBK locale; see DEVLOG pitfall 21).
- Run `deploy/quickstart.sh` from Git Bash or WSL (Docker Desktop with the WSL2 backend).

### Data & test notes

- **`src/dm/schema.py` is the single source of truth**: the 19-table model drives DDL, CDC SQL generation, data synthesis, and MCP introspection. To change CDC calibers, edit `src/dm/pipeline/gen_flink_cdc_sql.py` and regenerate `infra/cdc_*.sql` — never hand-edit the SQL.
- **Stable test IDs (frozen contract)**: `M0001` (total stock 12 @ `W02`), `SO0001` (needs `M0046`×265), `S001` (PO `PO0021`) — smoke, eval ground truths, and README demos all depend on them.
- **`TODAY = date(2026, 6, 25)`** (`dm/warehouse/generate.py`; a same-value copy lives in `dm/ontology/actions.py`) is a deliberate data anchor — eval SQL ground truths depend on it. **Never change it to `date.today()`**; on the dbt side the `anchor_today` var holds the same value and `current_date` is forbidden in models.
- **Debugging workflow**: the Streamlit console replays any session's task chain by `session_id` → locate the failing step (wrong table / wrong SQL / hallucination) → fix. It's a debugging tool, not just a showcase.

### PR guidelines

- **One PR does one thing** — no unrelated changes stacked together.
- Commit messages in Chinese or English, explaining *what changed and why*.
- Behavior changes need tests; new features should add eval cases (`src/dm/eval/eval_set.yaml`).
- Hit a new technical pitfall? Append *symptom + root cause + fix* to `docs/DEVLOG.md`.

### Docs language

Deep docs under `docs/` are currently Chinese-first; translation PRs are very welcome. The README stays bilingual.
