"""
AI 运维 API

供 Hermes / AI Agent 使用。
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ops.service import OpsService

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Depends
)

from ops.ops_auth import verify_ops_token

"""
router = APIRouter(
    prefix="/api/ops",
    tags=["AI运维"]
)
"""
#2026-8-31，适配AI新增代码
# api认证
# GET /api/ops/overview
# 必须:X-Ops-Token: xxx
router = APIRouter(
    prefix="/api/ops",
    tags=["AI运维"],
    dependencies=[
        Depends(verify_ops_token)
    ]
)


# 当前 Scheduler
_task_scheduler = None


def set_task_scheduler(task_scheduler):
    """
    设置当前 TaskScheduler。

    在 main.py startup 时调用。
    """
    global _task_scheduler
    _task_scheduler = task_scheduler


def get_ops_service() -> OpsService:
    """获取 OpsService"""

    return OpsService(
        task_scheduler=_task_scheduler
    )


# =========================================================
# Overview
# =========================================================

@router.get("/overview")
async def get_overview():
    """
    获取服务器整体概况。
    """

    try:

        service = get_ops_service()

        return {
            "success": True,
            "data": service.get_overview()
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"获取服务器概况失败: {str(e)}"
        }


# =========================================================
# Status
# =========================================================

@router.get("/status")
async def get_status():
    """
    获取服务器当前详细状态。
    """

    try:

        service = get_ops_service()

        return {
            "success": True,
            "data": service.get_server_status()
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"获取服务器状态失败: {str(e)}"
        }


# =========================================================
# Components
# =========================================================

@router.get("/components")
async def get_components():
    """
    获取所有组件状态。
    """

    try:

        service = get_ops_service()

        return {
            "success": True,
            "data": service.get_components()
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"获取组件状态失败: {str(e)}"
        }


@router.get("/components/{name}")
async def get_component_status(name: str):
    """
    获取指定组件状态。
    """

    service = get_ops_service()

    result = service.get_component_status(name)

    if result is None:

        raise HTTPException(
            status_code=404,
            detail=f"未找到组件: {name}"
        )

    return {
        "success": True,
        "data": result
    }


# =========================================================
# SSL
# =========================================================

@router.get("/ssl")
async def get_ssl_certificates(
    days: int = Query(
        30,
        ge=1,
        le=365
    )
):
    """
    获取即将过期的 SSL 证书。
    """

    try:

        service = get_ops_service()

        return {
            "success": True,
            "data": service.get_ssl_certificates(
                days=days
            )
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"获取SSL证书失败: {str(e)}"
        }


# =========================================================
# API
# =========================================================

@router.get("/apis")
async def get_api_status(
    status: str = Query(
        "all",
        pattern="^(all|normal|warning|critical)$"
    )
):
    """
    获取 API 监控状态。
    """

    try:

        service = get_ops_service()

        return {
            "success": True,
            "data": service.get_api_status(
                status=status
            )
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"获取API状态失败: {str(e)}"
        }


# =========================================================
# Alerts
# =========================================================

@router.get("/alerts")
async def get_alerts(
    hours: int = Query(
        24,
        ge=1,
        le=720
    ),
    level: str = Query(
        "all",
        pattern="^(all|warning|critical)$"
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200
    )
):
    """
    获取最近报警。
    """

    try:

        service = get_ops_service()

        return {
            "success": True,
            "data": service.get_alerts(
                hours=hours,
                level=level,
                limit=limit
            )
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"获取报警失败: {str(e)}"
        }


# =========================================================
# History
# =========================================================

@router.get("/history")
async def get_history(
    config_id: Optional[int] = Query(
        None,
        ge=1
    ),
    hours: int = Query(
        24,
        ge=1,
        le=720
    ),
    limit: int = Query(
        500,
        ge=1,
        le=2000
    )
):

    try:

        service = get_ops_service()

        return {
            "success": True,
            "data": service.get_history(
                config_id=config_id,
                hours=hours,
                limit=limit
            )
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"获取历史数据失败: {str(e)}"
        }


# =========================================================
# Trend
# =========================================================

@router.get("/trend")
async def get_metric_trend(
    metric: str = Query(
        ...,
        pattern="^(cpu|memory|disk|network)$"
    ),
    hours: int = Query(
        24,
        ge=1,
        le=720
    ),
    interval: str = Query(
        "1h",
        pattern="^(5m|15m|1h)$"
    )
):

    try:

        service = get_ops_service()

        return {
            "success": True,
            "data": service.get_metric_trend(
                metric=metric,
                hours=hours,
                interval=interval
            )
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"获取趋势失败: {str(e)}"
        }


# =========================================================
# Config
# =========================================================

@router.get("/configs")
async def get_monitor_configs():

    try:

        service = get_ops_service()

        return {
            "success": True,
            "data": service.get_monitor_configs()
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"获取监控配置失败: {str(e)}"
        }


# =========================================================
# Scheduler
# =========================================================

@router.get("/scheduler")
async def get_scheduler_status():

    try:

        service = get_ops_service()

        return {
            "success": True,
            "data": service.get_scheduler_status()
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"获取调度器状态失败: {str(e)}"
        }


# =========================================================
# Immediate Check
# =========================================================

@router.post("/check/{config_id}")
async def trigger_monitor_check(
    config_id: int
):

    try:

        service = get_ops_service()

        # 确认配置存在
        config = service.config_manager.get_monitor_config(
            config_id
        )

        if not config:

            raise HTTPException(
                status_code=404,
                detail="监控配置不存在"
            )

        success = await (
            service.trigger_monitor_check(
                config_id
            )
        )

        if not success:

            return {
                "success": False,
                "error": "立即检查失败，任务可能未运行"
            }

        return {
            "success": True,
            "message": "已触发立即检查",
            "config_id": config_id
        }

    except HTTPException:
        raise

    except Exception as e:

        return {
            "success": False,
            "error": f"立即检查失败: {str(e)}"
        }