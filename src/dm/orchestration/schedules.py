"""定时调度：U8+DW 全链路每 15 分钟；eval 每日 02:00。"""
from dagster import DefaultScheduleStatus, ScheduleDefinition

from dm.orchestration.jobs import job_eval_nightly, job_u8_dbt

schedule_u8_dbt = ScheduleDefinition(
    job=job_u8_dbt,
    cron_schedule="*/15 * * * *",
    execution_timezone="Asia/Shanghai",
    default_status=DefaultScheduleStatus.RUNNING,
)

schedule_eval_nightly = ScheduleDefinition(
    job=job_eval_nightly,
    cron_schedule="0 2 * * *",
    execution_timezone="Asia/Shanghai",
    default_status=DefaultScheduleStatus.RUNNING,
)
