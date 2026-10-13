# logger.py
"""
统一的日志配置模块
使用 loguru 进行日志管理
"""

import sys
import os
from pathlib import Path
from loguru import logger

# 创建日志目录
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 日志文件路径
LOG_FILE = LOG_DIR / "monitor_system.log"

# 移除默认的处理器
logger.remove()

# 控制台输出配置
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
    backtrace=True,
    diagnose=True
)

# 文件输出配置
logger.add(
    LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    encoding="utf-8",
    rotation="500 MB",
    retention="7 days",
    compression="zip",
    backtrace=True,
    diagnose=True,
    enqueue=True  # 异步写入，避免阻塞
)

# 错误日志单独文件
ERROR_LOG_FILE = LOG_DIR / "error.log"
logger.add(
    ERROR_LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR",
    encoding="utf-8",
    rotation="100 MB",
    retention="30 days",
    compression="zip",
    backtrace=True,
    diagnose=True,
    enqueue=True
)

# 导出 logger 实例
__all__ = ["logger"]