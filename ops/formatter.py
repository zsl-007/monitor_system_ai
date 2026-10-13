"""
AI 运维数据格式化模块

负责将监控系统内部的数据格式转换成
适合 AI Agent / Hermes 使用的数据格式。
"""

import json
from typing import Any, Dict


def parse_details(value: Any) -> Dict[str, Any]:
    """解析 monitor_data.details"""

    if not value:
        return {}

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            result = json.loads(value)
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    return {}


def format_monitor_config(row: Dict[str, Any]) -> Dict[str, Any]:
    """格式化监控配置"""

    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "type": row.get("type"),
        "target": row.get("target"),
        "enabled": bool(row.get("enabled")),
        "interval_seconds": row.get("interval_seconds"),
        "threshold": parse_details(row.get("threshold")),
        "extra_config": parse_details(row.get("extra_config")),
    }


def format_monitor_data(row: Dict[str, Any]) -> Dict[str, Any]:
    """格式化监控数据"""

    return {
        "id": row.get("id"),
        "config_id": row.get("config_id"),
        "name": row.get("config_name"),
        "type": row.get("monitor_type"),
        "value": row.get("value"),
        "status": row.get("status"),
        "is_normal": bool(row.get("is_normal")),
        "details": parse_details(row.get("details")),
        "created_time": row.get("created_time"),
    }


def format_alert(row: Dict[str, Any]) -> Dict[str, Any]:
    """格式化报警数据"""

    return {
        "id": row.get("id"),
        "config_id": row.get("config_id"),
        "config_name": row.get("config_name"),
        "monitor_type": row.get("monitor_type"),
        "message": row.get("alert_message"),
        "alert_time": row.get("alert_time"),
        "sent": bool(row.get("sent")),
    }