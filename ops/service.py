"""
AI 运维数据服务

该模块不负责 AI 推理，
只负责为 Hermes / AI Agent 提供统一、稳定、
结构化的服务器运维数据。
"""

import json
import socket
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from modules.database import (
    execute_query,
    execute_single
)

from modules.config import ConfigManager
from modules.alert import AlertManager

from ops.formatter import (
    format_monitor_config,
    format_monitor_data,
    format_alert,
    parse_details
)

from ops.health import calculate_health_score


class OpsService:
    """AI 运维数据服务"""

    def __init__(self, task_scheduler=None):
        self.task_scheduler = task_scheduler
        self.config_manager = ConfigManager()
        self.alert_manager = AlertManager()

    # =========================================================
    # 基础信息
    # =========================================================

    def get_server_info(self) -> Dict[str, Any]:
        """获取服务器基础信息"""

        try:
            hostname = socket.gethostname()

            return {
                "hostname": hostname,
                "project_name": self.config_manager.get_project_name(),
                "platform": self._get_platform()
            }

        except Exception as e:
            return {
                "hostname": "unknown",
                "project_name": self.config_manager.get_project_name(),
                "platform": "unknown",
                "error": str(e)
            }

    def _get_platform(self) -> str:
        """获取系统平台"""

        try:
            import platform
            return platform.platform()
        except Exception:
            return "unknown"

    # =========================================================
    # 当前状态
    # =========================================================

    def get_latest_monitor_data(self) -> List[Dict[str, Any]]:
        """获取所有启用监控项的最新数据"""

        query = '''
            SELECT
                md.*,
                mc.name AS config_name,
                mc.type AS monitor_type,
                mc.target AS target
            FROM monitor_data md
            INNER JOIN (
                SELECT
                    config_id,
                    MAX(created_time) AS max_time
                FROM monitor_data
                GROUP BY config_id
            ) latest
                ON md.config_id = latest.config_id
                AND md.created_time = latest.max_time
            INNER JOIN monitor_configs mc
                ON md.config_id = mc.id
            WHERE mc.enabled = 1
            ORDER BY mc.type, mc.name
        '''

        rows = execute_query(query)

        result = []

        for row in rows:
            item = format_monitor_data(row)

            item["target"] = row.get("target")

            result.append(item)

        return result

    def get_server_status(self) -> Dict[str, Any]:
        """获取服务器当前详细状态"""

        data = self.get_latest_monitor_data()

        resources = []
        components = []
        ssl_items = []
        api_items = []

        for item in data:

            monitor_type = item.get("type")

            if monitor_type in (
                "cpu",
                "memory",
                "disk",
                "network"
            ):
                resources.append(item)

            elif monitor_type == "component":
                components.append(item)

            elif monitor_type == "ssl":
                details = item.get("details", {})

                ssl_items.append({
                    "id": item.get("config_id"),
                    "name": item.get("name"),
                    "is_normal": item.get("is_normal"),
                    "level": details.get(
                        "level",
                        "normal"
                    ),
                    "days_remaining": details.get(
                        "days_remaining",
                        item.get("value")
                    ),
                    "expiry_date": details.get(
                        "expiry_date"
                    ),
                    "domain": details.get(
                        "domain",
                        item.get("target")
                    )
                })

            elif monitor_type == "api":
                details = item.get("details", {})

                api_items.append({
                    "id": item.get("config_id"),
                    "name": item.get("name"),
                    "is_normal": item.get("is_normal"),
                    "status_code": details.get(
                        "actual_status",
                        item.get("value")
                    ),
                    "response_time": details.get(
                        "response_time"
                    ),
                    "url": details.get(
                        "url",
                        item.get("target")
                    ),
                    "message": item.get("status")
                })

        alerts = self.get_alerts(
            hours=24,
            limit=100
        )

        health = calculate_health_score(
            resources=resources,
            components=components,
            ssl_items=ssl_items,
            api_items=api_items,
            alerts=alerts
        )

        return {
            "server": self.get_server_info(),

            "health": health,

            "resources": resources,

            "components": components,

            "ssl": ssl_items,

            "apis": api_items,

            "alerts": {
                "count": len(alerts),
                "items": alerts
            }
        }

    # =========================================================
    # Overview
    # =========================================================

    def get_overview(self) -> Dict[str, Any]:
        """获取服务器总体概况"""

        status = self.get_server_status()

        resources = status["resources"]
        components = status["components"]
        ssl_items = status["ssl"]
        apis = status["apis"]

        return {
            "server": status["server"],

            "health": status["health"],

            "resources": {
                "total": len(resources),
                "normal": sum(
                    1
                    for x in resources
                    if x.get("is_normal")
                ),
                "abnormal": sum(
                    1
                    for x in resources
                    if not x.get("is_normal")
                )
            },

            "components": {
                "total": len(components),
                "normal": sum(
                    1
                    for x in components
                    if x.get("is_normal")
                ),
                "abnormal": sum(
                    1
                    for x in components
                    if not x.get("is_normal")
                )
            },

            "ssl": {
                "total": len(ssl_items),
                "normal": sum(
                    1
                    for x in ssl_items
                    if x.get("is_normal")
                ),
                "abnormal": sum(
                    1
                    for x in ssl_items
                    if not x.get("is_normal")
                ),
                "expiring_30_days": sum(
                    1
                    for x in ssl_items
                    if (
                        x.get("days_remaining") is not None
                        and x.get("days_remaining") <= 30
                    )
                )
            },

            "apis": {
                "total": len(apis),
                "normal": sum(
                    1
                    for x in apis
                    if x.get("is_normal")
                ),
                "abnormal": sum(
                    1
                    for x in apis
                    if not x.get("is_normal")
                )
            },

            "alerts": status["alerts"]
        }

    # =========================================================
    # Components
    # =========================================================

    def get_components(self) -> List[Dict[str, Any]]:
        """获取所有组件状态"""

        data = self.get_latest_monitor_data()

        result = []

        for item in data:
            if item.get("type") != "component":
                continue

            details = item.get("details", {})

            result.append({
                "id": item.get("config_id"),
                "name": item.get("name"),
                "target": item.get("target"),
                "is_normal": item.get("is_normal"),
                "status": item.get("status"),
                "details": details,
                "created_time": item.get("created_time")
            })

        return result

    def get_component_status(
        self,
        name: str
    ) -> Optional[Dict[str, Any]]:
        """获取指定组件状态"""

        components = self.get_components()

        name_lower = name.lower()

        for item in components:

            target = str(
                item.get("target", "")
            ).lower()

            item_name = str(
                item.get("name", "")
            ).lower()

            if (
                target == name_lower
                or item_name == name_lower
                or name_lower in target
                or name_lower in item_name
            ):
                return item

        return None

    # =========================================================
    # SSL
    # =========================================================

    def get_ssl_certificates(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        获取 SSL 证书状态。

        返回所有 SSL 证书的统计信息，
        同时返回指定天数内即将过期的证书。

        例如：
            days=30

        表示：
            total    = 当前监控的 SSL 证书总数
            expiring = 30 天内即将过期的证书数量
            items    = 30 天内即将过期的证书
        """

        data = self.get_latest_monitor_data()

        # 所有 SSL 证书
        all_certificates = []

        # 即将过期的 SSL 证书
        expiring_certificates = []

        for item in data:

            if item.get("type") != "ssl":
                continue

            details = item.get("details", {})

            days_remaining = details.get(
                "days_remaining",
                item.get("value")
            )

            # 如果无法获得证书剩余天数，
            # 仍然保留证书基本信息，
            # 避免 AI 误认为不存在证书。
            certificate = {
                "id": item.get("config_id"),
                "name": item.get("name"),
                "domain": details.get(
                    "domain",
                    item.get("target")
                ),
                "port": details.get(
                    "port",
                    443
                ),
                "days_remaining": days_remaining,
                "expiry_date": details.get(
                    "expiry_date"
                ),
                "issuer": details.get(
                    "issuer"
                ),
                "subject": details.get(
                    "subject"
                ),
                "serial_number": details.get(
                    "serial_number"
                ),
                "signature_algorithm": details.get(
                    "signature_algorithm"
                ),
                "is_normal": item.get(
                    "is_normal"
                ),
                "status": item.get(
                    "status"
                ),
                "created_time": item.get(
                    "created_time"
                )
            }

            all_certificates.append(certificate)

            # 判断是否在指定天数内过期
            if (
                days_remaining is not None
                and days_remaining <= days
            ):
                expiring_certificates.append(
                    certificate
                )

        # 按剩余天数升序排列
        # 越快过期的排在越前面
        expiring_certificates.sort(
            key=lambda x: (
                x.get("days_remaining")
                if x.get("days_remaining") is not None
                else 999999
            )
        )

        return {
            "total": len(all_certificates),
            "expiring": len(expiring_certificates),
            "days": days,
            "items": expiring_certificates
        }

    # =========================================================
    # API
    # =========================================================

    def get_api_status(
        self,
        status: str = "all"
    ) -> List[Dict[str, Any]]:

        data = self.get_latest_monitor_data()

        result = []

        for item in data:

            if item.get("type") != "api":
                continue

            is_normal = bool(
                item.get("is_normal")
            )

            if status == "normal" and not is_normal:
                continue

            if status in (
                "warning",
                "critical"
            ):
                continue

            details = item.get(
                "details",
                {}
            )

            result.append({
                "id": item.get("config_id"),
                "name": item.get("name"),
                "url": details.get(
                    "url",
                    item.get("target")
                ),
                "method": details.get(
                    "method",
                    "GET"
                ),
                "is_normal": is_normal,
                "status_code": details.get(
                    "actual_status",
                    item.get("value")
                ),
                "response_time": details.get(
                    "response_time"
                ),
                "max_response_time": details.get(
                    "max_response_time"
                ),
                "message": item.get(
                    "status"
                ),
                "created_time": item.get(
                    "created_time"
                )
            })

        return result

    # =========================================================
    # Alerts
    # =========================================================

    def get_alerts(
        self,
        hours: int = 24,
        level: str = "all",
        limit: int = 50
    ) -> List[Dict[str, Any]]:

        hours = max(
            1,
            min(hours, 24 * 30)
        )

        limit = max(
            1,
            min(limit, 200)
        )

        alerts = self.alert_manager.get_recent_alerts(
            hours=hours,
            limit=limit
        )

        result = []

        for row in alerts:

            item = format_alert(row)

            message = str(
                item.get("message", "")
            ).upper()

            if level == "critical":
                if "[CRITICAL]" not in message:
                    continue

            elif level == "warning":
                if "[WARNING]" not in message:
                    continue

            result.append(item)

        return result

    # =========================================================
    # History
    # =========================================================

    def get_history(
        self,
        config_id: Optional[int] = None,
        hours: int = 24,
        limit: int = 500
    ) -> List[Dict[str, Any]]:

        hours = max(
            1,
            min(hours, 24 * 30)
        )

        limit = max(
            1,
            min(limit, 2000)
        )

        start_time = (
            datetime.now()
            - timedelta(hours=hours)
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        query = '''
            SELECT
                md.*,
                mc.name AS config_name,
                mc.type AS monitor_type,
                mc.target AS target
            FROM monitor_data md
            INNER JOIN monitor_configs mc
                ON md.config_id = mc.id
            WHERE md.created_time >= ?
        '''

        params = [start_time]

        if config_id is not None:
            query += " AND md.config_id = ?"
            params.append(config_id)

        query += '''
            ORDER BY md.created_time DESC
            LIMIT ?
        '''

        params.append(limit)

        rows = execute_query(
            query,
            tuple(params)
        )

        result = []

        for row in rows:

            item = format_monitor_data(row)

            item["target"] = row.get(
                "target"
            )

            result.append(item)

        return result

    # =========================================================
    # Trend
    # =========================================================

    def get_metric_trend(
        self,
        metric: str,
        hours: int = 24,
        interval: str = "1h"
    ) -> Dict[str, Any]:
        """获取指标趋势"""

        config_type = metric.lower()

        allowed_metrics = {
            "cpu",
            "memory",
            "disk",
            "network"
        }

        if config_type not in allowed_metrics:
            raise ValueError(
                f"不支持的指标: {metric}"
            )

        hours = max(
            1,
            min(hours, 24 * 30)
        )

        interval_minutes = {
            "5m": 5,
            "15m": 15,
            "1h": 60
        }.get(interval, 60)

        start_time = (
            datetime.now()
            - timedelta(hours=hours)
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # SQLite 时间聚合
        if interval_minutes == 5:
            time_group = (
                "strftime('%Y-%m-%d %H:', created_time)"
                " || printf('%02d', "
                "CAST(strftime('%M', created_time) AS INTEGER) / 5 * 5)"
            )

        elif interval_minutes == 15:
            time_group = (
                "strftime('%Y-%m-%d %H:', created_time)"
                " || printf('%02d', "
                "CAST(strftime('%M', created_time) AS INTEGER) / 15 * 15)"
            )

        else:
            time_group = (
                "strftime('%Y-%m-%d %H:00:00', created_time)"
            )

        query = f'''
            SELECT
                datetime({time_group}) AS time_bucket,
                AVG(value) AS avg_value,
                MIN(value) AS min_value,
                MAX(value) AS max_value,
                COUNT(*) AS sample_count
            FROM monitor_data
            WHERE monitor_type = ?
              AND created_time >= ?
              AND value IS NOT NULL
            GROUP BY time_bucket
            ORDER BY time_bucket
        '''

        rows = execute_query(
            query,
            (
                config_type,
                start_time
            )
        )

        samples = []

        for row in rows:

            samples.append({
                "time": row["time_bucket"],
                "value": round(
                    row["avg_value"],
                    2
                ) if row["avg_value"] is not None else None,
                "min": round(
                    row["min_value"],
                    2
                ) if row["min_value"] is not None else None,
                "max": round(
                    row["max_value"],
                    2
                ) if row["max_value"] is not None else None,
                "sample_count": row[
                    "sample_count"
                ]
            })

        values = [
            x["value"]
            for x in samples
            if x["value"] is not None
        ]

        if values:
            minimum = min(values)
            maximum = max(values)
            average = sum(values) / len(values)
            latest = values[-1]

            if len(values) >= 2:

                first = values[0]

                difference = latest - first

                if difference > max(
                    abs(first) * 0.1,
                    1
                ):
                    trend = "increasing"

                elif difference < -max(
                    abs(first) * 0.1,
                    1
                ):
                    trend = "decreasing"

                else:
                    trend = "stable"

            else:
                trend = "unknown"

        else:

            minimum = None
            maximum = None
            average = None
            latest = None
            trend = "no_data"

        #2026-8-31，适配AI新增代码  #解决检测项单位问题
        unit_map = {
            "cpu": "%",
            "memory": "%",
            "disk": "%",
            "network": "bytes/s"
        }

        return {
            "metric": config_type,
            "unit": unit_map.get(
                config_type,
                ""
            ),
            "period_hours": hours,
            "interval": interval,
            "min": minimum,
            "max": maximum,
            "avg": round(
                average,
                2
            ) if average is not None else None,
            "latest": latest,
            "trend": trend,
            "sample_count": len(samples),
            "samples": samples
        }

    # =========================================================
    # Monitor Config
    # =========================================================

    def get_monitor_configs(
        self
    ) -> List[Dict[str, Any]]:

        configs = (
            self.config_manager
            .get_all_monitor_configs()
        )

        return [
            format_monitor_config(
                x
            )
            for x in configs
        ]

    # =========================================================
    # Scheduler
    # =========================================================

    def get_scheduler_status(
        self
    ) -> Dict[str, Any]:

        if not self.task_scheduler:

            return {
                "running": False,
                "task_count": 0,
                "tasks": [],
                "execution_stats": {}
            }

        return {
            "running": bool(
                self.task_scheduler.scheduler.running
            ),
            "task_count": len(
                self.task_scheduler.jobs
            ),
            "tasks": (
                self.task_scheduler
                .get_running_tasks()
            ),
            "execution_stats": (
                self.task_scheduler
                .get_execution_stats()
            )
        }

    # =========================================================
    # Immediate Check
    # =========================================================

    async def trigger_monitor_check(
        self,
        config_id: int
    ) -> bool:

        if not self.task_scheduler:
            return False

        return await (
            self.task_scheduler
            .trigger_immediate_check(
                config_id
            )
        )