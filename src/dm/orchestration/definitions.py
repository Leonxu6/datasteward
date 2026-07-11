"""Dagster Definitions（workspace 入口）：资产 + 作业 + 调度 + 传感器 + dbt 资源。"""
from dagster import Definitions

from dm.orchestration.assets_dbt import dbt_resource, dm_dbt_assets
from dm.orchestration.assets_u8 import u8_assets
from dm.orchestration.jobs import job_docs_kg_rebuild, job_eval_nightly, job_u8_dbt
from dm.orchestration.schedules import schedule_eval_nightly, schedule_u8_dbt
from dm.orchestration.sensors import health_alert_sensor

defs = Definitions(
    assets=[*u8_assets, dm_dbt_assets],
    jobs=[job_u8_dbt, job_docs_kg_rebuild, job_eval_nightly],
    schedules=[schedule_u8_dbt, schedule_eval_nightly],
    sensors=[health_alert_sensor],
    resources={"dbt": dbt_resource},
)
