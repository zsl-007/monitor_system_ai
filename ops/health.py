"""
服务器健康评分模块
"""

from typing import Dict, Any, List


def calculate_health_score(
    resources: List[Dict[str, Any]],
    components: List[Dict[str, Any]],
    ssl_items: List[Dict[str, Any]],
    api_items: List[Dict[str, Any]],
    alerts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    根据当前监控状态计算服务器健康评分。

    该评分仅作为 AI 辅助指标，
    不代表服务器实际“健康百分比”。
    """

    score = 100
    reasons = []

    # -------------------------
    # 系统资源
    # -------------------------

    for item in resources:
        level = item.get("level")

        if level == "critical":
            score -= 15
            reasons.append(
                f"{item.get('name', item.get('type'))}处于严重状态"
            )

        elif level == "warning":
            score -= 5
            reasons.append(
                f"{item.get('name', item.get('type'))}处于警告状态"
            )

    # -------------------------
    # 组件
    # -------------------------

    for item in components:
        if not item.get("is_normal", True):
            score -= 15
            reasons.append(
                f"组件 {item.get('name', 'unknown')} 状态异常"
            )

    # -------------------------
    # SSL
    # -------------------------

    for item in ssl_items:
        days = item.get("days_remaining")

        if days is None:
            continue

        if days <= 7:
            score -= 15
            reasons.append(
                f"SSL证书 {item.get('name')} 剩余 {days} 天"
            )
        elif days <= 30:
            score -= 5
            reasons.append(
                f"SSL证书 {item.get('name')} 剩余 {days} 天"
            )

    # -------------------------
    # API
    # -------------------------

    for item in api_items:
        if not item.get("is_normal", True):
            score -= 10
            reasons.append(
                f"API {item.get('name')} 状态异常"
            )

    # -------------------------
    # 报警
    # -------------------------

    critical_alerts = sum(
        1
        for alert in alerts
        if "[CRITICAL]" in str(alert.get("message", "")).upper()
    )

    warning_alerts = sum(
        1
        for alert in alerts
        if "[WARNING]" in str(alert.get("message", "")).upper()
    )

    score -= min(critical_alerts * 10, 30)
    score -= min(warning_alerts * 3, 15)

    score = max(0, min(100, score))

    if score >= 90:
        level = "healthy"
        description = "服务器整体运行正常"

    elif score >= 70:
        level = "warning"
        description = "服务器存在部分需要关注的问题"

    else:
        level = "critical"
        description = "服务器存在较严重异常"

    return {
        "score": score,
        "level": level,
        "description": description,
        "reasons": reasons[:20]
    }