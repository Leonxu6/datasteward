# 设计文档 · 对标 Palantir Foundry 的治理体系研究与落地映射

> 本目录是 DataSteward 的**权威设计文档集**：以 Palantir Foundry 的公开资料为对标基准，讲透其**架构、心智模型与第一性原理**，并给出**在本平台开源栈上的落地映射**——它既是设计依据，也是开发蓝图。
>
> 来源：一次深度调研工作流（9 维度并行调研 Palantir 官方公开文档 + 对**权限/审计/血缘**三块做多源对抗验证，与官方逐字核对）。硬细节（字段名、枚举、阈值、JSON schema）尽量忠实照录；对抗验证发现的更正已吸收进正文。Palantir、Foundry 为 Palantir Technologies 的商标，本项目与其无任何关联。

## 阅读顺序

| 篇 | 标题 | 讲什么 | 对应我们平台的层 |
|---|---|---|---|
| **[00](./00-第一性原理与心智模型.md)** | 第一性原理与心智模型 | **为什么**这么设计（先读这篇） | 全局 |
| [01](./01-数据连接层-Data-Connection.md) | 数据连接层 Data Connection | 连接器：多源接入、凭据、源打标、增量/CDC | `connect/` |
| [02](./02-管道与数据集-Transforms-Datasets.md) | 管道与数据集 Transforms & Datasets | ELT 抽取清洗转化、raw/refined 分层、版本化 | `datasets/` + `pipeline/` |
| [03](./03-Ontology本体层.md) | Ontology 本体层 | 对象/属性/链接/**Action**/函数（Palantir 的灵魂） | `ontology/` |
| [04](./04-血缘-Lineage.md) | 数据血缘 Lineage | 表级/列级血缘 + **安全随血缘传播** | `pipeline/lineage.py` |
| [05](./05-权限与Markings.md) | 权限与 Markings | 强制+自主两层 AND、行/列粒度、**写回权限** | `security/` |
| [06](./06-审计-Audit.md) | 审计 Audit | append-only、分类全表、who/what/when/why+trace | `connector/` + `store.py` |
| [07](./07-数据健康与监控-Data-Health.md) | 数据健康与监控 Data Health | 监控目录（信号/阈值/告警）、坏数据门禁 | `health/` |
| [08](./08-应用层-Workshop-与管理者视图.md) | 应用层 Workshop 与管理者视图 | 操作应用/报表字段规格 + Control Panel | `app/pages/*` |
| [09](./09-AIP-与-Ontology-Actions.md) | AIP 与 Ontology Actions | 行动闭环（**我们用智能体 agent 实现 AIP**） | `agent/` + `ontology/actions.py` |
| **[SPEC.md](./SPEC.md)** | 实装级复刻 spec | **照着实现**：逐子系统数据模型/接口/字段/阈值 + 栈上落地映射 + 决策点 | 开发依据 |

## 核心一句话

> 在数据之上建一个**能被治理、能被行动的世界模型**，让每一次"看"和每一次"改"都**可控、可溯、可信**。（展开见 [00](./00-第一性原理与心智模型.md)）
