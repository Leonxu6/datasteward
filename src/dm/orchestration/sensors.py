"""Health alert sensor with stable cursors and retry-safe notifications."""
from dagster import DefaultSensorStatus, SensorEvaluationContext, SkipReason, sensor

from dm.orchestration.health_alerts import failure_cursor, normalize_failures, render_failure_alert

_RECOVERY_MESSAGE = "✅ 数据健康告警解除：全部检查恢复正常"
_PUSH_FAILURE = "钉钉推送失败，保留原 cursor 以便下次重试"


@sensor(
    name="health_alert_sensor",
    minimum_interval_seconds=300,
    default_status=DefaultSensorStatus.RUNNING,
    description="健康检查 fail → 钉钉群告警（cursor 去重，恢复后自动解除）",
)
def health_alert_sensor(context: SensorEvaluationContext):
    from dm.channels.dingtalk import push_webhook
    from dm.health.checks import run_all

    failures = normalize_failures(run_all())

    if not failures:
        if context.cursor and context.cursor != "[]":
            try:
                push_webhook(_RECOVERY_MESSAGE)
            except Exception:  # notification backend details are not sensor output
                return SkipReason(_PUSH_FAILURE)
        context.update_cursor("[]")
        return SkipReason("健康检查全部通过")

    cursor = failure_cursor(failures)
    if cursor == context.cursor:
        return SkipReason(f"告警未变化（{len(failures)} 项 fail），不重复推送")

    try:
        push_webhook(render_failure_alert(failures))
    except Exception:
        return SkipReason(_PUSH_FAILURE)

    context.update_cursor(cursor)
    return SkipReason(f"已推送 {len(failures)} 项数据健康告警")
