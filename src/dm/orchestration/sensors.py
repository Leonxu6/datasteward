"""健康告警传感器：每 5 分钟跑健康检查目录，出现 fail 即推钉钉群（带去重光标）。

检查目录复用 dm/health/checks.py（volume/expectation/parity/schema/freshness——
其中 parity=源汇对账，正是 CDC 顿挫探测器）。
"""
import json

from dagster import DefaultSensorStatus, SensorEvaluationContext, SkipReason, sensor


@sensor(
    name="health_alert_sensor",
    minimum_interval_seconds=300,
    default_status=DefaultSensorStatus.RUNNING,
    description="健康检查 fail → 钉钉群告警（cursor 去重，恢复后自动解除）",
)
def health_alert_sensor(context: SensorEvaluationContext):
    from dm.channels.dingtalk import push_webhook
    from dm.health.checks import run_all

    summary = run_all()
    fails = [r for r in summary.get("results", []) if r.get("status") == "fail"]
    fail_ids = sorted(r.get("id", "?") for r in fails)
    cursor = json.dumps(fail_ids, ensure_ascii=False)

    if not fails:
        if context.cursor and context.cursor != "[]":
            try:
                push_webhook("✅ 数据健康告警解除：全部检查恢复正常")
            except Exception:  # noqa: BLE001
                pass
        context.update_cursor("[]")
        return SkipReason("健康检查全部通过")

    if cursor == context.cursor:
        return SkipReason(f"告警未变化（{len(fails)} 项 fail），不重复推送")

    lines = [f"🚨 数据健康告警（{len(fails)} 项 fail）："]
    for r in fails[:8]:
        lines.append(f"· [{r.get('id')}] {r.get('message', '')}")
    lines.append("详见管理台「数据健康」页")
    try:
        push_webhook("\n".join(lines))
        context.update_cursor(cursor)
    except Exception as e:  # noqa: BLE001
        return SkipReason(f"钉钉推送失败：{e}")
