# scheduler.py
"""
任务调度器模块
负责动态加载监控配置并创建定时任务
支持配置变更时的任务动态更新
"""

import asyncio
#import logging
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.job import Job

from monitors.system import SystemMonitor
from monitors.ssl import SSLMonitor
from monitors.api import APIMonitor
from monitors.component import ComponentMonitor

from modules.config import ConfigManager
from modules.alert import AlertManager

import random
import json

from modules.database import execute_insert  # 新增导入

# 使用统一的日志配置
from .logger import logger
# 移除原有的 logging 配置
# 配置日志
#logging.basicConfig(level=logging.INFO)
#logger = logging.getLogger(__name__)

class TaskScheduler:
    """任务调度器 - 带任务队列版本"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        
        # 配置调度器
        job_defaults = {
            'coalesce': False,
            'max_instances': 3,
            'misfire_grace_time': 30
        }
        
        self.scheduler = AsyncIOScheduler(job_defaults=job_defaults)
        self.jobs: Dict[int, Job] = {}
        self.monitors = {
            'cpu': SystemMonitor(),
            'memory': SystemMonitor(),
            'disk': SystemMonitor(),
            'network': SystemMonitor(),
            'ssl': SSLMonitor(),
            'api': APIMonitor(),
            'component': ComponentMonitor()
        }
        
        # 任务执行队列和信号量
        self.task_semaphore = asyncio.Semaphore(5)  # 同时执行的最大任务数
        self.pending_tasks = set()
        
        # 初始化报警管理器
        self.alert_manager = AlertManager()
        
        # 存储上次监控状态
        self.last_status: Dict[int, bool] = {}

        # 任务执行统计
        self.execution_stats = {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'timeout_executions': 0,
            'missed_executions': 0,
            'last_execution_time': None
        }        
        
        logger.info("任务调度器初始化完成")
		
    async def _clean_old_data(self):
        """清理超过保留天数的数据"""
        try:
            from datetime import datetime, timedelta
            from database import get_db_connection

            retention_days = self.config_manager.get_data_retention_days()
            cutoff_date = datetime.now() - timedelta(days=retention_days)

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM monitor_data WHERE created_time < ?', (cutoff_date,))
                monitor_deleted = cursor.rowcount
                cursor.execute('DELETE FROM alert_data WHERE alert_time < ?', (cutoff_date,))
                alert_deleted = cursor.rowcount
                conn.commit()

            logger.info(f"数据清理完成，删除了{retention_days}天前的监控数据{monitor_deleted}条，报警数据{alert_deleted}条")
        except Exception as e:
            logger.error(f"数据清理失败: {e}")  

    async def start(self):
        """启动调度器"""
        try:
            # 添加数据清理任务，每天凌晨2点执行
            """
            self.scheduler.add_job(
                self._clean_old_data,
                'cron',
                hour=2,
                minute=0,
                id='data_cleanup',
                name='清理旧数据',
                replace_existing=True
            )
            """

            # 加载初始配置并创建任务
            await self.load_and_schedule_tasks()
            
            # 启动调度器
            self.scheduler.start()
            logger.info("任务调度器启动成功")
            
            # 启动配置变化监听（简化版本，实际可以轮询或使用事件）
            asyncio.create_task(self._watch_config_changes())
            
        except Exception as e:
            logger.error(f"启动调度器失败: {e}")
            raise
    
    async def stop(self):
        """停止调度器"""
        try:
            self.scheduler.shutdown()
            self.jobs.clear()
            self.last_status.clear()
            logger.info("任务调度器已停止")
        except Exception as e:
            logger.error(f"停止调度器失败: {e}")
    
    async def load_and_schedule_tasks(self):
        """加载所有启用的监控配置并创建定时任务"""
        try:
            configs = self.config_manager.get_enabled_monitor_configs()
            logger.info(f"加载到 {len(configs)} 个启用的监控配置")
            
            for config in configs:
                await self._create_monitor_task(config)
                
        except Exception as e:
            logger.error(f"加载和调度任务失败: {e}")
    
    async def _create_monitor_task(self, config: Dict[str, Any]):
        """为单个监控配置创建定时任务"""
        try:
            config_id = config['id']
            monitor_type = config['type']
            interval = config['interval_seconds']
            
            # 如果任务已存在，先移除
            if config_id in self.jobs:
                self._remove_monitor_task(config_id)
            
            # 为相同间隔的任务添加随机延迟，避免同时触发
            jitter = random.randint(0, min(10, interval // 2))  # 最大10秒的随机延迟
            
            # 创建定时任务
            job = self.scheduler.add_job(
                self._execute_monitor,
                'interval',
                seconds=interval,
                args=[config],
                id=str(config_id),
                name=f"{monitor_type}_{config_id}",
                replace_existing=True,
                jitter=jitter  # 添加随机延迟
            )
            
            self.jobs[config_id] = job
            logger.info(f"创建监控任务: {config['name']} (ID: {config_id}, 间隔: {interval}秒, 延迟: {jitter}秒)")
            
        except Exception as e:
            logger.error(f"创建监控任务失败 {config['name']}: {e}")
    
    def _remove_monitor_task(self, config_id: int):
        """移除单个监控任务"""
        try:
            if config_id in self.jobs:
                job = self.jobs[config_id]
                job.remove()
                del self.jobs[config_id]
                
                # 清理状态记录
                if config_id in self.last_status:
                    del self.last_status[config_id]
                
                logger.info(f"移除监控任务: ID {config_id}")
        except Exception as e:
            logger.error(f"移除监控任务失败 {config_id}: {e}")
    
    async def _execute_monitor(self, config: Dict[str, Any]):
        """执行监控任务 - 带队列控制版本"""
        config_id = config['id']
        
        # 如果任务已经在执行中，跳过
        if config_id in self.pending_tasks:
            logger.debug(f"任务已在执行中，跳过: {config['name']} (ID: {config_id})")
            return
        
        try:
            # 标记任务为执行中
            self.pending_tasks.add(config_id)
            
            # 使用信号量控制并发
            async with self.task_semaphore:
                await self._execute_monitor_internal(config)
                
        except Exception as e:
            logger.error(f"执行监控任务失败 {config.get('name', 'Unknown')}: {e}")
        finally:
            # 移除执行标记
            if config_id in self.pending_tasks:
                self.pending_tasks.remove(config_id)
    
    async def _execute_monitor_internal(self, config: Dict[str, Any]):
        """内部执行监控任务"""

        """内部执行监控任务 - 带统计"""
        start_time = time.time()
        config_id = config['id']

        try:
            config_id = config['id']
            monitor_type = config['type']
            monitor_name = config['name']
            
            logger.debug(f"执行监控: {monitor_name} (ID: {config_id})")
            
            # 获取对应的监控器
            monitor = self.monitors.get(monitor_type)
            if not monitor:
                logger.error(f"不支持的监控类型: {monitor_type}")
                return
            
            # 使用超时控制
            timeout_seconds = max(10, config.get('interval_seconds', 60) * 0.8)
            
            try:
                # 执行监控（带超时）
                result = await asyncio.wait_for(
                    monitor.check(config), 
                    timeout=timeout_seconds
                )
                
                # 处理监控结果
                await self._handle_monitor_result(config, result)
                
            except asyncio.TimeoutError:
                logger.error(f"监控任务超时: {monitor_name} (ID: {config_id})")
                error_result = {
                    'is_normal': False,
                    'message': f"监控任务执行超时（>{timeout_seconds}秒）"
                }
                await self._handle_monitor_result(config, error_result)

            # 更新统计
            self.execution_stats['total_executions'] += 1
            self.execution_stats['successful_executions'] += 1
            self.execution_stats['last_execution_time'] = time.time()                

        except asyncio.TimeoutError:
            # 更新超时统计
            self.execution_stats['total_executions'] += 1
            self.execution_stats['timeout_executions'] += 1
            self.execution_stats['last_execution_time'] = time.time()
            # ... 处理超时 ...
                
        except Exception as e:
            logger.error(f"执行监控任务失败 {config.get('name', 'Unknown')}: {e}")
            error_result = {
                'is_normal': False,
                'message': f"监控任务执行异常: {str(e)}"
            }
            await self._handle_monitor_result(config, error_result)  
            # 更新失败统计
            self.execution_stats['total_executions'] += 1
            self.execution_stats['failed_executions'] += 1
            self.execution_stats['last_execution_time'] = time.time()
            # ... 处理异常 ...

        finally:
            # 记录执行时间
            execution_time = time.time() - start_time
            if execution_time > 1.0:  # 如果执行时间超过1秒，记录警告
                logger.warning(f"监控任务执行时间较长: {config['name']} - {execution_time:.2f}秒")              
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """获取任务执行统计"""
        return self.execution_stats.copy()
    
    async def _handle_monitor_result(self, config: Dict[str, Any], result: Dict[str, Any]):
        """处理监控结果 - 更新版本，集成报警"""
        try:
            config_id = config['id']
            monitor_type = config['type']
            
            # 检查是否需要报警
            alert_record = self.alert_manager.check_threshold(config, result)
            
            if alert_record:
                # 发送报警邮件
                email_sent = await self.alert_manager.send_alert_email(alert_record)
                alert_record.sent = email_sent
                
                # 保存报警记录
                self.alert_manager.save_alert_record(alert_record)
                
                logger.warning(f"触发报警: {alert_record.alert_message}")
            
            # 记录监控结果到数据库
            await self._save_monitor_data(config, result)
            
            # 记录状态变化（用于日志）
            current_status = result.get('is_normal', True)
            last_status = self.last_status.get(config_id)
            
            if last_status is None or last_status != current_status:
                status_text = "正常" if current_status else "异常"
                logger.info(f"状态变化: {config['name']} -> {status_text}")
                self.last_status[config_id] = current_status
            
        except Exception as e:
            logger.error(f"处理监控结果失败: {e}")

    async def _save_monitor_data(self,config: Dict[str, Any],result: Dict[str, Any]):
        """保存监控数据到数据库"""

        try:
            value = result.get('value')
            status = result.get('message', '')
            is_normal = result.get('is_normal', True)

            # 保存 Monitor 返回的详细信息   #2026-8-31，适配AI新增代码
            details = result.get('details', {})

            # JSON 序列化   #2026-8-31，适配AI新增代码
            try:
                details_json = json.dumps(
                    details,
                    ensure_ascii=False,
                    default=str
                )
            except Exception:
                details_json = '{}'

            # 使用本地时间
            created_time = datetime.now().strftime(
                '%Y-%m-%d %H:%M:%S'
            )

            execute_insert('''
                INSERT INTO monitor_data
                (
                    config_id,
                    monitor_type,
                    value,
                    status,
                    is_normal,
                    details,
                    created_time
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                config['id'],
                config['type'],
                value,
                status,
                is_normal,
                details_json,   #2026-8-31，适配AI新增代码
                created_time
            ))

        except Exception as e:
            logger.error(f"保存监控数据失败: {e}")

    async def _trigger_alert(self, config: Dict[str, Any], result: Dict[str, Any]):
        """触发报警"""
        try:
            alert_message = f"监控项 {config['name']} 检测到异常"
            
            if 'message' in result:
                alert_message += f": {result['message']}"
            elif 'value' in result:
                alert_message += f", 当前值: {result['value']}"
            
            logger.warning(f"触发报警: {alert_message}")
            
            # TODO: 调用报警模块发送邮件
            # TODO: 将报警记录存储到数据库
            
        except Exception as e:
            logger.error(f"触发报警失败: {e}")
    
    async def _watch_config_changes(self):
        """监听配置变化（简化版本，通过轮询实现）"""
        logger.info("启动配置变化监听")
        
        last_check = time.time()
        last_config_count = len(self.jobs)
        
        while True:
            try:
                # 每30秒检查一次配置变化
                await asyncio.sleep(30)
                
                current_time = time.time()
                if current_time - last_check < 30:
                    continue
                
                last_check = current_time
                
                # 检查配置数量变化
                enabled_configs = self.config_manager.get_enabled_monitor_configs()
                current_config_count = len(enabled_configs)
                
                if current_config_count != last_config_count:
                    logger.info(f"检测到配置数量变化: {last_config_count} -> {current_config_count}")
                    await self._sync_tasks_with_config(enabled_configs)
                    last_config_count = current_config_count
                else:
                    # 检查单个配置的变化
                    await self._check_individual_config_changes(enabled_configs)
                    
            except Exception as e:
                logger.error(f"配置变化监听异常: {e}")
                await asyncio.sleep(60)  # 出错时等待时间长一些
    
    async def _sync_tasks_with_config(self, enabled_configs: List[Dict[str, Any]]):
        """同步任务与配置"""
        try:
            enabled_ids = {config['id'] for config in enabled_configs}
            current_ids = set(self.jobs.keys())
            
            # 找出需要添加的任务
            to_add = enabled_ids - current_ids
            for config_id in to_add:
                config = next((c for c in enabled_configs if c['id'] == config_id), None)
                if config:
                    await self._create_monitor_task(config)
            
            # 找出需要移除的任务
            to_remove = current_ids - enabled_ids
            for config_id in to_remove:
                self._remove_monitor_task(config_id)
                
        except Exception as e:
            logger.error(f"同步任务与配置失败: {e}")
    
    async def _check_individual_config_changes(self, enabled_configs: List[Dict[str, Any]]):
        """检查单个配置的变化"""
        try:
            for config in enabled_configs:
                config_id = config['id']
                
                if config_id not in self.jobs:
                    continue
                
                job = self.jobs[config_id]
                
                # 检查间隔是否变化
                current_interval = config['interval_seconds']
                job_interval = job.trigger.interval.total_seconds()
                
                if abs(current_interval - job_interval) > 1:  # 允许1秒的误差
                    logger.info(f"检测到监控间隔变化: {config['name']} ({job_interval} -> {current_interval})")
                    await self._create_monitor_task(config)  # 重新创建任务
    
        except Exception as e:
            logger.error(f"检查配置变化失败: {e}")
    
    # 公共方法，供外部调用
    
    def get_running_tasks(self) -> List[Dict[str, Any]]:
        """获取当前运行的任务列表"""
        tasks = []
        for config_id, job in self.jobs.items():
            next_run = job.next_run_time
            if next_run:
                # 格式化时间，移除时区信息
                if hasattr(next_run, 'strftime'):
                    next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    next_run_str = str(next_run).split('+')[0]  # 移除时区信息
            else:
                next_run_str = "未知"
                
            tasks.append({
                'config_id': config_id,
                'name': job.name,
                'next_run_time': next_run_str,
                'interval': job.trigger.interval.total_seconds() if job.trigger else 0
            })
        return tasks

    async def trigger_immediate_check(self, config_id: int) -> bool:
        """立即触发指定配置的检查"""
        try:
            if config_id in self.jobs:
                job = self.jobs[config_id]
                job.modify(next_run_time=datetime.now())
                logger.info(f"立即触发检查: {job.name}")
                return True
            else:
                logger.warning(f"未找到运行中的任务: {config_id}")
                return False
        except Exception as e:
            logger.error(f"立即触发检查失败 {config_id}: {e}")
            return False
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        return {
            'running': self.scheduler.running,
            'task_count': len(self.jobs),
            'next_wakeup': self.scheduler._wakeup.time if hasattr(self.scheduler, '_wakeup') else None
        }