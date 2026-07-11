"""数据源接入层：影子源（被 CDC 的"假 ERP/MES"）与变更注入。

- seed_source.py：把合成数据灌入 Postgres 影子源（OLTP 表 + 逻辑复制就绪）。
- mutate.py：对影子源持续制造增删改，演示 CDC 实时同步（S1）。
"""
