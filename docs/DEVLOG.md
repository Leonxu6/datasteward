# 开发日志 / 踩坑记录（DEVLOG）

> 约定：开发中遇到的**技术坑 + 根因 + 解法**沉淀在此，避免重复踩坑。新坑往对应小节追加。
> 数据 plane 的生产参考环境是一台 aarch64 一体机（GB10，119GB 内存），dm 全容器化部署（详见根 README 与 deploy/docker-compose.yml）。

---

## 十层重构 + GB10 部署（2026-07-07）

### ★ 坑15：国内直连 maven central "慢速僵死"卡死整条部署链
**现象**：`curl repo1.maven.org` 拉 Flink CDC jar 到 4% 后速率归零但连接不断，无超时的 curl 挂 6 分钟后被对端 reset；Clash 代理线路同样 26% 断流。
**解法**（infra/flink-lib/download.sh）：镜像顺序 **maven.aliyun.com 优先** → central 直连 → central 经代理；所有 curl 一律 `-m 600` 超时 + sha256 校验 + 失败清理重试。

### 坑16：pgrep -f 自匹配——`bash -c "pgrep -f 'deploy.sh' || 启动"` 永远"已在跑"
**根因**：`bash -c` 的命令串本身含匹配模式，pgrep -f 匹配到发起判定的这条命令。两次误判导致部署实际没启动。
**解法**：判定改 `ps -eo args | grep -E '^bash deploy/deploy.sh' | grep -v grep`（锚定命令行首）；或用 marker 文件。

### 坑17：azure-sql-edge 两连坑（仿真 U8 源）
- healthcheck 写 `CMD-SHELL "</dev/tcp/..."` 永远 unhealthy——CMD-SHELL 走 /bin/sh(dash)，`/dev/tcp` 是 bash 特性 → 用 `["CMD","bash","-c","exec 3<>/dev/tcp/127.0.0.1/1433"]`。
- 镜像不带 sqlcmd → 建库/DDL/灌数一律经 TDS 客户端（pymssql）外灌（sources/seed_u8_sim.py 即为此而生）。

### 坑18：paramiko exec_command 跑 `setsid/nohup … &` 偶发吊死 read
**现象**：远端进程明明起来了，本端 `stdout.read()` 却 PipeTimeout。
**解法**：**启动与观测分离**——发射命令容忍超时，另开连接用 `ps + tail 日志` 确认；长任务一律 `setsid … </dev/null > log 2>&1 &` + 日志轮询，绝不依赖发射通道的返回。

### ★ 坑19：ollama 自建模型 TEMPLATE 无 tools 分支 → tool-calling 全废
**现象**：自建 Modelfile 的 35B 模型（qwen35moe 34.7B Q8_0）capabilities 只有 `['completion']`，带 tools 的请求被 ollama 400 拒；LiteLLM 配置还指向已删除的 tag（`qwen3.6:35b-a3b-bf16`）→ 网关 500。
**解法**：**同一 GGUF blob + 官方带-tools template 秒建新模型**（零下载）：抓 registry 上 qwen3 的 template 层 blob → `ollama create qwen3-tools -f Modelfile`（FROM 指向已有 blob 路径）→ capabilities 变 `['completion','tools','thinking']`；同步修 litellm_config.yaml（改前备份）并 `docker restart litellm-gateway`。教训：**网关配置里的模型名要与 `ollama list` 实况对账**。

### 坑20：protobuf gencode/runtime 版本方向性
dagster 的 grpc-health gencode 7.35 遇 dbt pin 的 protobuf<7（runtime 6.33）直接崩：**runtime 不得旧于 gencode**；反向（runtime 7.35 + dbt gencode 6.x）合法。解法：升 protobuf≥7.35，无视 dbt 的元数据 pin（实测兼容）。

### 坑21：Windows 本地跑 dbt GBK 解码崩
dbt 读模型文件按 locale（GBK）→ 中文注释炸 `UnicodeDecodeError`。解法：`PYTHONUTF8=1`（容器内天然 UTF-8 无此坑）。

### ★ 坑22：azure-sql-edge 在新内核 aarch64 上 sqlservr 单核空转不监听
**现象**：容器 Up 但 1433/1431 全拒连；`ps` 显示 sqlservr 99.8% CPU 烧单核十几分钟不 bind。page size 4096 正常、镜像 arm64 正确——deprecated 的 SQL Edge 在 6.17 新内核上的已知死法，等不来的。
**解法**：仿真 U8 弃 sql-edge，改**备用 x86 主机跑 mssql 2022 Express**（更贴近真实 U8），aarch64 主机经 systemd 自愈 SSH 隧道（0.0.0.0:21433）访问；compose 的 sim-u8 转 profile 停用（x86 上可正常启用）。

### ★ 坑23：paramiko exec_command 的复合后台启动被吞 + pkill/pgrep 自匹配家族
**现象**：`bash -c "pkill -f 'x'; setsid daemon & echo ok"` 三连坑——①pkill 模式匹配到载着它的 bash -c 自身 → 把自己杀了（`21433:127.0.0.1:21433` 这种字面量最典型）；②即便活着，`&` 后的检查输出也常被通道吞；③发射通道 read 假超时但远端进程实际已启动。
**解法**：守护进程一律 **systemd 单元**（或 systemd-run 一次性单元），不赌 setsid；判定进程用 `ps -eo args | grep -E '^bash x.sh'` 锚定行首或 `[.]` 正则技巧；发射与观测**分离**（发射容忍超时，另开连接查 ps+日志）。

### 坑24：容器里跑批"看起来 0 进度"——stdout 管道缓冲
`docker compose run dm-cli dm-eval > log` 时 Python print 进管道全缓冲，日志迟迟不落 ≠ 没在跑。**看 JSONL 侧写**（eval_run.jsonl 每例 append 直写）判断真实进度；要实时 stdout 加 `PYTHONUNBUFFERED=1`。

### ★ 坑25：ollama 容器 GPU 挂载"静默失效"——35B 在 CPU 上爬
**现象**：compose 里 GPU reservation 配置齐全，但跑了 3 天的旧容器 `ollama ps` 显示 100% **CPU**（35B 每问一两分钟）；nvidia-smi 无 ollama 进程。
**解法**：`docker compose up -d --force-recreate ollama` 即恢复 100% GPU（32.9GB 显存驻留，单问 17s）。教训：**推理容器要例行核对 `ollama ps` 的 PROCESSOR 列**，别拿"容器在跑"当"GPU 在跑"。

### ★ 坑29：LiteLLM 是"取消黑洞"——客户端断开不取消上游，流式根治被中间层拦腰截断
**现象**：V-1 僵尸复现实验（生成中 `docker rm -f` 客户端）：经 LiteLLM 的流式长生成在杀死客户端后**继续跑满 67s**（接近自然完成）；同实验改**直连 ollama /v1** 后，杀点即止损（日志耗时 7.99s≈杀点，秒级传导）。
**根因**：LiteLLM 收到 client disconnect 后停止读上游但不关闭/取消上游请求（httpx 连接挂起，ollama 写缓冲不满就一直生成）——取消传导链在网关处断裂。
**解法**：**智能体主链路直连 ollama 的 OpenAI 兼容端点 `:11434/v1`**（compose 的 DM_LLM_BASE_URL 写死直连；模型名用 ollama 原名 `qwen3.6:35b-a3b`），断开一跳直达推理后端；LiteLLM 退居云备选（deepseek）场景。字段差异：思考文本 LiteLLM=`reasoning_content`、ollama /v1=`reasoning`——graph.py `_reasoning_of()` 双兼容。哨兵探针同步改打直连端点。
**教训**：**取消传导要逐跳实证**，"客户端断开→上游止损"在每个中间层都可能断，别默认代理会转发取消。

### 坑28：GB10 sshd "TCP 握手成功但 5 秒静默断开、banner 零字节"——SSH 整体不可用
**现象**：paramiko 报 `Error reading SSH protocol banner`；原始 socket 测试连接成功但 recv 5.0s 后收到空（对端 FIN），三连皆同；ping/3389 正常，系统活着。
**根因推断**：sshd 未认证连接堆积触发 MaxStartups 静默丢弃（paramiko 运维模式=每脚本新建 SSH 连接、高频且偶有异常退出不 close），或 socket-activation 后端 spawn 失败。正常 sshd 哪怕过载也会先吐 banner——**零 banner+定时断开=前端在丢弃，不是网络问题**。
**解法**：等 LoginGraceTime（2 分钟）自清理后重试；不行走 RDP（3389）进桌面 `systemctl restart ssh`。**预防**：paramiko 脚本 finally 必 close；高频运维复用一条连接（或改用长驻隧道进程的 transport）。

### 坑26：GB10 桌面版 Ubuntu 默认"自动休眠"——生产一体机会睡死
RDP 登录弹 "Automatic suspend: Suspending soon because of inactivity"。解法（已做）：`sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target`。

### ★ 坑27：重建 ollama 的"在途请求"变僵尸，占死并发槽 100 分钟——下游全体假死
**现象**：eval C5-C12 连挂 8 例全是 `Request timed out`，钉钉提问无响应；但网关/容器网络三视角测试全通、宿主小请求秒回——"看起来都健康，就是没人回答"。
**根因（铁证）**：`docker logs ollama` 出现两条 **`500 | 1h40m0s | POST /api/chat`**——force-recreate ollama 那一刻正在处理的两个请求变成孤儿，客户端已死但服务端持续"生成"，把 `OLLAMA_NUM_PARALLEL=2` 的并发槽**全部占死约 100 分钟**（直到自身超时），期间所有新请求排队等死。**深层机理：非流式请求的取消不传导**——客户端超时/死亡后连接挂着没人读也没人写，LiteLLM 与 ollama 都感知不到，生成照跑。
**判法**：疑似 LLM 假死先看 `docker logs ollama` 有没有超长耗时的在途请求，别被"网关 200"骗了。
**解法（应急）**：`docker restart ollama` 立斩僵尸（模型重载约 1 分钟）；**重建/重启 ollama 前先停掉正在跑的推理消费方**（eval/长会话）；eval 一律独占窗口跑（02:00 夜跑的意义）；被污染的 run 作废重跑，不拿去下结论。
**根治（PR⑧ 已落地）**：**全链路流式取消传导**——graph.py `_invoke_llm` 手写 stream 循环（墙钟超时即 `gen.close()`）、dm/llm.py `chat()` requests stream=True；流式下 ollama 每个 token 都要写连接，任何一环断开→写失败→**生成当场中止、槽位当场释放**，僵尸物理上无法形成。配套分层超时（connect 10s / token 间隔 60s / 墙钟 240s，全 env 可调）+ `DM_LLM_STREAMING=0` 应急回退 + systemd 哨兵 `dm-llm-watchdog.timer`（流式探针两连败只告警，`WATCHDOG_AUTO_RESTART` 默认关）。
**ollama 槽位变更 runbook**（NUM_PARALLEL/CONTEXT_LENGTH 调整，1Panel compose）：①低峰窗口先停消费方（dm-dingtalk/dm-app，确认无 eval）②`cp docker-compose.yml{,.bak-日期}` ③改 environment ④`up -d --force-recreate` ⑤`ollama ps` 核对 100% GPU+显存 ⑥并发小请求验证 ⑦恢复消费方跑 smoke；1Panel 面板同步登记参数防应用升级覆盖手改。

---

## S3：知识图谱（Neo4j：结构化 FK 骨架 + 文档抽取关系 → graph_query）

### 坑12：主机 docker 镜像源集体超时，拉不动 neo4j
**现象**：daemon mirror（daocloud/1panel/rat.dev）+ 手点 xuanyuan/1ms/dockerpull 全部拉 neo4j 超时、`Pulling fs layer` 卡住无字节（早先拉 StarRocks/Flink 是好的，属当晚网络抖动）。
**解法**：主机挂自愈重拉循环 `until docker pull neo4j:5-community; do sleep 40; done; docker compose --profile kg up -d neo4j`（nohup 后台），网络一恢复自动起。compose 里 neo4j 用 `profiles:[kg]` 按需起、堆/页缓存压到 512m/384m 适配 4C/8G。

### 坑13：复合主键表做 FK 目标时按"被引用表 PK 首列属性"匹配
**现象**：`purchase_arrival.po_id → purchase_order`，但 purchase_order 是复合 PK(po_id+line_no)、节点 id=`po_id#line_no`，FK 值只有 po_id → 按 id 匹配不上。
**解法**：建边时目标节点按 `b.<ref_pk0>=fk值` 匹配（ref_pk0=被引用表 PK 首列，正好等于 FK 列名语义），单主键也通用；复合目标会一对多 fan-out（到该 PO 的所有行），语义可接受。

### 坑14：graph_query 沿用 search_documents 的隔离套路
neo4j 驱动同样**别在 stdio-MCP 的 asyncio 事件循环里直跑**——graph_query 也走 async 子进程 `dm.kg.graph_cli` + `stdin=DEVNULL` + 单行 `DMJSON:` 取结果（同坑11四件套）。驱动 notification 噪声（coalesce 引可选属性 title 的 property-not-exist 警告）用 `notifications_min_severity="OFF"` 关掉。

## S2：非结构化 RAG（合成文档 → 本地嵌入 → pgvector → search_documents）

### 坑8：Windows 上 fastembed/HF 缓存符号链接权限（WinError 1314）
**现象**：fastembed 首次下载 bge 模型后，再开进程加载报 `Could not find tokenizer_config.json in …Temp\fastembed_cache\…`——onnx 模型在、tokenizer 配置丢了。
**根因**：huggingface_hub 缓存默认用符号链接把 blob 链到 snapshot；Windows 非管理员/未开开发者模式无权限建符号链接（WinError 1314），小文件链接失败 → 缓存残缺；且默认缓存落 `%TEMP%`，清理后每次重下。
**解法**（`dm/docs/embed.py`，**须在 import fastembed 之前**设）：`HF_HUB_DISABLE_SYMLINKS=1`（改为复制）+ 固定缓存目录 `~/.cache/dm_fastembed`（非 Temp）。模型 `BAAI/bge-small-zh-v1.5`（512 维，~90MB，CPU）。

### 坑9：纯向量检索对"实体专属"问题区分力弱 → 混合检索
**现象**：6 份措辞高度相似的采购合同，问"供应商 S001 的违约金"反而命中 S003 合同（向量分仅差 ~0.01）。
**根因**：bge 把"采购合同+违约金"语义压得很近，"S001/S003"这类 ID 差异对句向量几乎无影响。
**解法**（`dm/docs/search.py`）：混合检索——向量取较宽候选（top_k×3），再对"查询里的实体 ID（S001/M0001/PA0001/CNC-08…）命中片段关联实体"加权重排（+0.15/命中）。锚点命中率 4/5 → **6/6**；无 ID 的查询退化为纯向量、不受影响。

### 坑10：pgvector 接线
- 镜像 `pgvector/pgvector:pg16` 自带扩展，但需在业务库（默认 dm） `CREATE EXTENSION vector` 一次（否则 register_vector 找不到 vector 类型）。
- psycopg2 传/取向量要 `from pgvector.psycopg2 import register_vector`；列类型 `vector(512)`；余弦近邻 `embedding <=> %s`，建 HNSW `vector_cosine_ops` 索引。
- 文档表 `document/doc_chunk` 与 19 张业务表**同库不同表**；Flink CDC 按表建作业、只抓那 19 张，doc_* 不受影响（"一个 Postgres 一身三职"：CDC 源 + 向量库 + 元数据）。

### ★ 坑11：stdio-MCP 里跑"原生库 + 子进程"把 JSON-RPC 通道搞崩（search_documents 卡死 agent）
**现象**：agent 问文档题，任务链记录了 `tool_call: search_documents` 却永远等不到结果（卡几分钟）；
`list_tables`/`run_sql` 同服务器却正常。MCP 协议级复现：`list_tools` 成功，一调 `search_documents`
就 `anyio.BrokenResourceError`，连接断。
**根因链**（stdio-MCP 的 **stdout 就是 JSON-RPC 通道**，且 FastMCP 跑在 asyncio）：
1. `search_documents` 在事件循环里直接跑 **onnxruntime(C++ 写 fd1)/psycopg2** 等原生库 →
   污染/打断 stdout 的 JSON-RPC（`list_tables` 走 pymysql 纯 Python、快，幸免）。
2. 改用同步 `subprocess.run` 隔离 → 在 Windows proactor 事件循环里与子进程管道争用**死锁**（卡满 90s 超时）。
3. 改 `asyncio.create_subprocess_exec`（异步子进程，与循环协作）→ 仍超时：子进程**继承了 MCP 服务器的
   stdin（claude→server 的 JSON-RPC 管道）** → 在 Windows 上与 `communicate()` 争用卡死。
**解法**（四件套缺一不可，见 `connector/mcp_server.py` + `docs/search_cli.py` + `docs/embed.py`）：
- 检索放**干净子进程** `python -m dm.docs.search_cli`，原生库不进 MCP 服务器进程；
- 用 **async** 子进程 `asyncio.create_subprocess_exec`（不要 `subprocess.run`）；
- **`stdin=asyncio.subprocess.DEVNULL`**（关键！否则继承 JSON-RPC stdin 卡死）；
- `embed.py` 里 fd 级 `_silence_stdout`（fd1→fd2），保证子进程 stdout 只剩一行 `DMJSON:` 结果；
- agent 经 mcp-config 注入 `DM_EMBED_CACHE` + `HF_HUB_OFFLINE=1`，子进程离线读预下好的模型缓存。
**结果**：agent 自主串联 `run_sql`+`search_documents`（各 ~2.2s）→ 正确引用 DOC0001 作答并标注 chunk 出处。
**通用教训**：stdio-MCP 工具里**凡涉及原生库/子进程**，一律隔离到 async 子进程 + `stdin=DEVNULL` + 净化 stdout；
绝不让任何非 JSON-RPC 字节碰 fd1。

## S1：Flink CDC（Postgres 影子源 → StarRocks）

### ★ 坑1：StarRocks allin1 跨容器 Stream Load 失败（最大的坑，耗时最久）
**现象**：Flink CDC 作业 `RUNNING` 但数据不进 StarRocks；checkpoint 反复失败；
TM 报 `Connect to 127.0.0.1:8040 ... Connection refused`，作业在 `RUNNING↔RESTARTING` 崩溃循环。

**根因链**：
- StarRocks Stream Load 协议：客户端 POST 到 **FE(8030)** → FE 返回 307 **重定向到某个 BE 的 `<be_ip>:8040`** → 客户端把数据发给 BE。
- allin1 镜像 `entrypoint.sh` 用 `append_if_missing` 把 FE/BE 的 `priority_networks` 写死 `127.0.0.1/32`；`director/run.sh` 里 `MYHOST=127.0.0.1`，把 BE 注册成 `127.0.0.1:9050`。
- 于是 FE 把 Flink 重定向到 `127.0.0.1:8040`——从 Flink 容器看 `127.0.0.1` 是它自己，不可达。

**解法**（已 durable 写进 `infra/docker-compose.yml` 的 starrocks `entrypoint` 包装器）：
启动原 entrypoint 前，把 FE/BE 的 `priority_networks` 与 director 的 `MYHOST` 都改成**容器 IP**（从 `/etc/hosts` 读）。全新初始化时三者一致用容器 IP，FE 重定向到 `<容器IP>:8040`，Flink 同网络可达。

**附带卡了很久的几个子坑**：
1. **Docker Compose 会对 compose 文件里的 `$` 做变量插值**，把 entrypoint 脚本里的 `$(...)`/`$IP`/`$1` 吃成空（症状：`priority_networks = /32`、`MYHOST=` 全空，BE FATAL）。→ compose 里所有要传给 shell 的 `$` **必须写成 `$$`**。
2. `hostname -i` / `hostname -I` 在容器 entrypoint 刚启动那刻可能**返回空**。→ 改从 `/etc/hosts` 读容器 IP：`grep -E '^[0-9]+\.' /etc/hosts | grep -v '^127\.' | awk '{print $1}'`。
3. Stream Load 的 `load-url` **必须是 FE(8030)，不能直接用 BE(8040)**：直连 BE 时连接器调 `get_load_state` 接口，BE 没有 → `404 Not Found`。
4. `ALTER SYSTEM DROP BACKEND` 删唯一 BE 被拒（单副本系统表保护）→ 需加 `FORCE`。
5. FE 与 BE 地址必须同类：FE 在 `127.0.0.1`、BE 在容器 IP 会报 `FE heartbeat with localhost ip but BE is not deployed on the same machine` 或 `FE saved address not match backend address`。所以 **FE 和 BE 的 priority_networks 要一起改**。

**排查命令**：`SHOW BACKENDS\G`(看 IP/Alive/HttpPort)、Flink REST `/jobs/<id>/exceptions`、
`docker logs dm-flink-tm`、BE 日志 `/data/deploy/starrocks/be/log/be.WARNING`、director `/data/deploy/starrocks/director/run.sh`。

### 坑2：Postgres 逻辑复制（CDC 源）准备
- `wal_level=logical` + `max_replication_slots`/`max_wal_senders` 调大（19 表各一 slot，设 30）；compose 用 `command: [postgres, -c, wal_level=logical, ...]` 传参。
- 建表后 `ALTER TABLE ... REPLICA IDENTITY FULL`，UPDATE/DELETE 才有完整 before-image。
- postgres-cdc 用 `decoding.plugin.name=pgoutput`（内置，免装插件）；每个源表 `slot.name` 唯一。

### 坑3：连接器版本匹配
- **Flink 1.18 + `flink-sql-connector-postgres-cdc:3.0.1` + `flink-connector-starrocks:1.2.9_flink-1.18`**。
- jar 用阿里云 Maven 镜像下载快；**文件级 bind mount** 进 `/opt/flink/lib`（免自建镜像，且不覆盖原 lib）。

---

## S0：DuckDB → StarRocks

### 坑4：标识符引用方言
DuckDB 用双引号 `"table"`，StarRocks(MySQL 方言)用**反引号** `` `table` ``；双引号在 StarRocks 是字符串字面量 → `list_tables`/数据预览报 `1064` 语法错。mcp_server/app/load 全改反引号。

### 坑5：StarRocks 主键模型（为 CDC upsert 预留）
建表 `PRIMARY KEY (...) DISTRIBUTED BY HASH(...) BUCKETS 1 PROPERTIES("replication_num"="1")`；
pk 列必须**在最前且 NOT NULL**（schema.py 已保证）；单 BE 必须 `replication_num=1`。

### 坑6：pymysql 薄适配器保接口
StarRocks 走 MySQL 协议，用 pymysql 包一层暴露 DuckDB 风格接口
（`execute().fetchone/fetchmany/fetchall/fetchdf/.description` + `close`），mcp_server/app/eval 取数代码零改动。

---

## 通用 / 环境

### 坑7：阿里云主机 + Docker
- 拉大镜像（StarRocks ~5GB）易断 → **重试循环**；`/etc/docker/daemon.json` 配国内 mirror（daocloud 等）。
- Windows 本机 **5432 端口被占** → Postgres 隧道用 `15432→5432`。
- 轻量服务器实际 4C/8G（非建议的 8C/32G），分阶段起组件、内存调小；StarRocks 空载仅 ~1.3G。

---

## Palantir 复刻（Phase 0–2）

### 坑：SSH 隧道被主机反复踢断
长任务（15min eval）中隧道报 `Connection closed by remote host`（exit 255），致其后所有 DB 依赖用例**连续假失败**。
普通 `ssh -N` 不自恢复 → 改**自愈隧道**：`while true; do ssh -N ...; sleep 3; done` 后台循环，断线 3s 自动重连。
诊断信号：失败用例呈**连续区块**（如 C11–C19 全红，含上一轮通过的用例）= 基建掉线，非代码回归。

### 坑：`rag` 可选依赖 fastembed 未装 → RAG 静默失败
`search_documents` 抛 `ModuleNotFoundError: fastembed`，RAG 全簇 eval 变红、但 refusal 类反而"通过"（检索空→答"未提及"）。
根因是环境缺 `.[rag]`；`pip install fastembed pgvector numpy` 修复。**嵌入模型缓存存在 ≠ 包已装**。

### 坑：pip editable `dm` 指向别的 worktree
`pip install -e` 的 `dm` 可能指到另一个 worktree；直接 `python -m dm.x` 会跑**错代码**（报缺新符号）。
跨 worktree 开发一律 `PYTHONPATH=src python -m dm.x` 强制用当前 worktree。

### 坑：PBAC 引入后 eval 默认目的会误伤 FIN 用例
PURPOSE_REQUIRED 对 FIN 施加目的门控后，eval 默认 `purpose` 若不在 FIN 允许集，则**管理员也拿不到 FIN 列**。
解法：run_eval 默认 `purpose=财务对账`（对 FIN 有效），权限反例用例再显式设不正当目的触发拦截。

### 坑：本体 get_links 入向链接键冲突
多子表外键派生成同名关系（如都叫 `material`），入向链接以 `api_name` 作字典键会互相覆盖（8 条只剩 1）。
改用 `子对象.关系` 唯一键。E2E 对活库才暴露——单元测试因单表看不出。

### 坑：create 类 Action 的生成 ID 在 pending→approve 两步不一致
`create_purchase_requisition`/`create_delivery` 待审批与审批各调一次 `_new_id()` → 预览与实际写入 ID 不同。
解法：pending 时把生成的 ID 存进 `params`（`_po_id`/`_delivery_id`），approve 复用。E2E（对活库验主键）才暴露。

### 坑：run_sql 行级策略用"视图替换"最稳
向任意 SQL 注入行级过滤很脆（有 join/子查询）。改把受限表的 `FROM/JOIN t` 替换为
`FROM (SELECT * FROM t WHERE col='v') t`（别名保表名，后续列引用不变），原 SQL 其余不动。

### 技巧：CDC 顿挫探测 = 源↔汇行数对账
`parity` 检查比对 PG(源) 与 StarRocks(汇) 行数，不等即 CDC 延迟/停摆告警。E2E 演示：PG 插临时行→
对账立刻报差 1（趁 CDC 未追上）→ 追平后恢复→清理。用非 eval 物料避免干扰并行 eval。

### 坑（严重）：清理测试数据的 LIKE 删除撞了真实 ID 前缀 → 误删真实数据
create_delivery 生成的临时发货单用 `DN<timestamp>`，而**真实发货单也是 `DN%`**（生成器 `DN{i:04d}`）。
`DELETE ... WHERE delivery_id LIKE 'DN%'` 把 25 行真实发货单一并删了。教训：
① 清理只删**精确 ID**（从 action_log 取本次创建的 id 逐条删），不要用宽前缀 LIKE；
② 测试/占位数据用**绝不与真实撞**的前缀（如 `ZZTEST_`）。
恢复：合成数据确定性（SEED=42+固定日期），`build_all()['delivery_note']` 重生成同样 25 行灌回 PG，CDC 同步回 StarRocks，健康对账恢复一致。**确定性造数是数据事故的安全网**。

### 技巧：接客户库 onboarding = 自省 + 对照本体的就绪报告
`dm-connect onboard <source>` 用连接器 `introspect()` 读真库元数据，对照 Ontology 给"N/M 表已建模、
X 表待建模"。真 U8 配 `DM_SRC_MSSQL_*` 即插；这是"接上就能用"的最小人工步骤（客户给连接凭据/DDL）。

### 坑：给用户的错误回执直接取返回体首行 → 推出一个 "{"
钉钉"人话化"回执把内核失败转述给用户时，最初 `s.splitlines()[0]`（纯文本拒绝如 `⛔ 权限不足：…` 首行即人话）。
但 execute_action 失败返回 **indent=2 美化 JSON**（首行只有 `{`），且 `"权限不足"` 出现在原文前 200 字内，
纯文本分支先命中 → 用户收到一条 `{`。解法：先 `json.loads` 判形态，错误文案一律取 `error` 字段首行；
纯文本分支只在 JSON 解析不成立时走。教训：**转述"内核返回"给人看时，先判结构再取文案，绝不可拿原文首行赌**。
（发现路径：E2E 对抗例真发权限被拒场景，钉钉真机看到 `{`；单测复刻同形态后回归。）

### 坑：Windows tar 的 -f 参数会把 `C:\...` 当远程主机
Git Bash 的 GNU tar 见 `-czf C:\Users\...` 报 `Cannot connect to C: resolve failed`（冒号=远程语法）。
解法：`cwd=目标目录` + 相对路径 `-czf dm_src.tgz`；或 `--force-local`（bsdtar 无此坑，但 PATH 里哪个 tar 先命中不可控）。

### 坑：合成数据"双时钟"——数据锚冻结而墙钟漂移 + 状态随机穿越
数据的"今天"=造数锚 2026-06-25（TODAY/dbt anchor_today，eval 真值依赖，勿改），但系统墙钟一直走。
两个叠加症状：① 造数状态纯随机不看日期 → "delivery_date=07-09 已签收"穿越行；② 模型用
CURRENT_DATE()（墙钟）解释"明天" → 组合成"明天的发货已完成，无需担心"的荒诞答案（用户实报）。
解法：① generate.py 未来日期行事后矫正状态（发货→待发/到货→待检），**rng 调用序逐一对齐保持随机流** 
不漂移（稳定 ID M0001/SO0001/S001 单测作金丝雀）；② `DM_ANCHOR_TODAY` 注入 SYSTEM，相对时间以数据锚
推算（接真库留空回归墙钟）；③ 生产存量数据用同语义 UPDATE 原地收敛（纯 DML 走 CDC，避免 seed_source
 的 DROP 在 CDC 运行中断流）。教训：**演示数据必须整体活在一个时钟里，凡随机生成的状态字段都要过
一遍"日期允许吗"**。
