# monitors/system.py
"""
系统资源监控器
CPU、内存、磁盘、网络监控 - 完整实现
"""

import psutil
import asyncio
from typing import Dict, Any, Tuple
from monitors.base import BaseMonitor

from typing import Dict, Any, Tuple, List  # 添加 List 导入

class SystemMonitor(BaseMonitor):
    """系统资源监控器 - 优化版本"""
    
    def __init__(self):
        self.last_network_stats = {}
        self.last_network_time = None
        self.last_cpu_time = None
    
    async def check(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查系统资源"""
        try:
            monitor_type = config['type']
            threshold_config = config.get('threshold', {})
            target = config.get('target', '')
            
            if monitor_type == 'cpu':
                return await self._check_cpu(threshold_config)
            elif monitor_type == 'memory':
                return await self._check_memory(threshold_config)
            elif monitor_type == 'disk':
                return await self._check_disk(target, threshold_config)
            elif monitor_type == 'network':
                return await self._check_network(target, threshold_config)
            else:
                return {
                    'is_normal': False,
                    'message': f"不支持的监控类型: {monitor_type}"
                }
                
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"系统监控异常: {str(e)}"
            }

    async def _check_impl(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查系统资源 - 优化实现"""
        monitor_type = config['type']
        threshold_config = config.get('threshold', {})
        target = config.get('target', '')
        
        if monitor_type == 'cpu':
            return await self._check_cpu(threshold_config)
        elif monitor_type == 'memory':
            return await self._check_memory(threshold_config)
        elif monitor_type == 'disk':
            return await self._check_disk(target, threshold_config)
        elif monitor_type == 'network':
            return await self._check_network(target, threshold_config)
        else:
            return {
                'is_normal': False,
                'message': f"不支持的监控类型: {monitor_type}"
            }
            
    async def _check_cpu(self, threshold: Dict[str, Any]) -> Dict[str, Any]:
        """检查CPU使用率 - 完整实现"""
        """检查CPU使用率 - 优化版本"""
        try:
            # 获取CPU使用率，间隔1秒获取更准确的数据
            #usage = psutil.cpu_percent(interval=1)
            # 使用更短的间隔获取CPU使用率，提高响应速度
            usage = psutil.cpu_percent(interval=0.5)            
            warning = threshold.get('warning', 80)
            critical = threshold.get('critical', 90)
            
            is_normal = usage < warning
            level = 'normal'
            if usage >= critical:
                level = 'critical'
            elif usage >= warning:
                level = 'warning'
            
            # 获取更多CPU信息
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
            
            return {
                'is_normal': is_normal,
                'value': round(usage, 2),
                'level': level,
                'message': f"CPU使用率: {usage:.1f}%",
                'details': {
                    'logical_cores': cpu_count,
                    'current_frequency': round(cpu_freq.current, 2) if cpu_freq else 0,
                    'load_1min': round(load_avg[0], 2) if load_avg else 0,
                    'load_5min': round(load_avg[1], 2) if load_avg else 0,
                    'load_15min': round(load_avg[2], 2) if load_avg else 0
                }
            }
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"CPU监控失败: {str(e)}"
            }
    
    async def _check_memory(self, threshold: Dict[str, Any]) -> Dict[str, Any]:
        """检查内存使用率 - 完整实现"""
        try:
            memory = psutil.virtual_memory()
            usage = memory.percent
            warning = threshold.get('warning', 80)
            critical = threshold.get('critical', 90)
            
            is_normal = usage < warning
            level = 'normal'
            if usage >= critical:
                level = 'critical'
            elif usage >= warning:
                level = 'warning'
            
            # 获取交换分区信息
            swap = psutil.swap_memory()
            
            return {
                'is_normal': is_normal,
                'value': round(usage, 2),
                'level': level,
                'message': f"内存使用率: {usage:.1f}% ({self._bytes_to_gb(memory.used):.1f}GB/{self._bytes_to_gb(memory.total):.1f}GB)",
                'details': {
                    'total_gb': self._bytes_to_gb(memory.total),
                    'used_gb': self._bytes_to_gb(memory.used),
                    'available_gb': self._bytes_to_gb(memory.available),
                    'swap_total_gb': self._bytes_to_gb(swap.total),
                    'swap_used_gb': self._bytes_to_gb(swap.used),
                    'swap_percent': round(swap.percent, 2)
                }
            }
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"内存监控失败: {str(e)}"
            }
    
    def get_disk_partitions(self) -> List[Dict[str, Any]]:
        """获取所有磁盘分区信息"""
        try:
            partitions = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    partitions.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'opts': partition.opts,
                        'total_gb': self._bytes_to_gb(usage.total),
                        'used_gb': self._bytes_to_gb(usage.used),
                        'free_gb': self._bytes_to_gb(usage.free),
                        'percent': usage.percent
                    })
                except (PermissionError, FileNotFoundError):
                    # 跳过无法访问的分区（如CD-ROM等）
                    continue
            return partitions
        except Exception as e:
            print(f"获取磁盘分区失败: {e}")
            return []

    async def _check_disk(self, target: str, threshold: Dict[str, Any]) -> Dict[str, Any]:
        """检查磁盘使用率 - 完整实现"""
        try:
            # 如果target为空，使用根目录
            mount_point = target if target else '/'

            # 检查挂载点是否存在
            try:
                disk_usage = psutil.disk_usage(mount_point)
            except FileNotFoundError:
                return {
                    'is_normal': False,
                    'message': f"磁盘挂载点不存在: {mount_point}"
                }            
            
            usage = psutil.disk_usage(mount_point).percent
            warning = threshold.get('warning', 80)
            critical = threshold.get('critical', 90)
            
            is_normal = usage < warning
            level = 'normal'
            if usage >= critical:
                level = 'critical'
            elif usage >= warning:
                level = 'warning'
            
            disk_usage = psutil.disk_usage(mount_point)
            disk_io = psutil.disk_io_counters()
            
            return {
                'is_normal': is_normal,
                'value': round(usage, 2),
                'level': level,
                'message': f"磁盘使用率: {usage:.1f}% ({self._bytes_to_gb(disk_usage.used):.1f}GB/{self._bytes_to_gb(disk_usage.total):.1f}GB)",
                'details': {
                    'mount_point': mount_point,
                    'total_gb': self._bytes_to_gb(disk_usage.total),
                    'used_gb': self._bytes_to_gb(disk_usage.used),
                    'free_gb': self._bytes_to_gb(disk_usage.free),
                    'read_bytes': disk_io.read_bytes if disk_io else 0,
                    'write_bytes': disk_io.write_bytes if disk_io else 0
                }
            }
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"磁盘监控失败 {target}: {str(e)}"
            }

    def get_network_interfaces(self) -> List[Dict[str, Any]]:
        """获取所有网络接口信息"""
        try:
            stats = psutil.net_io_counters(pernic=True)
            interfaces = []
            
            for interface_name, interface_stats in stats.items():
                # 跳过环回接口和虚拟接口
                if interface_name.startswith(('lo', 'Loopback', 'Software Loopback Interface')):
                    continue
                    
                interfaces.append({
                    'name': interface_name,
                    'bytes_sent': interface_stats.bytes_sent,
                    'bytes_recv': interface_stats.bytes_recv,
                    'packets_sent': interface_stats.packets_sent,
                    'packets_recv': interface_stats.packets_recv,
                    'errin': interface_stats.errin,
                    'errout': interface_stats.errout,
                    'dropin': interface_stats.dropin,
                    'dropout': interface_stats.dropout,
                    'is_active': (interface_stats.bytes_sent > 0 or interface_stats.bytes_recv > 0)
                })
            
            # 按活动状态排序，活跃接口在前
            interfaces.sort(key=lambda x: not x['is_active'])
            
            return interfaces
        except Exception as e:
            print(f"获取网络接口失败: {e}")
            return []
        
    async def _check_network(self, target: str, threshold: Dict[str, Any]) -> Dict[str, Any]:
        """检查网络流量 - 完整实现，计算实时速率"""
        try:
            # 获取所有网络接口统计
            stats = psutil.net_io_counters(pernic=True)

            # 如果未指定接口，使用第一个活动接口
            if not target:
                # 找到有流量的第一个接口
                for interface, interface_stats in stats.items():
                    if interface_stats.bytes_sent > 0 or interface_stats.bytes_recv > 0:
                        target = interface
                        break
                if not target:
                    target = list(stats.keys())[0] if stats else 'lo'
            
            if target not in stats:
                return {
                    'is_normal': False,
                    'message': f"网络接口不存在: {target}"
                }
            
            current_stats = stats[target]
            current_time = asyncio.get_event_loop().time()
            
            # 计算速率
            sent_rate = 0
            recv_rate = 0
            total_rate = 0
            
            if target in self.last_network_stats and self.last_network_time:
                time_diff = current_time - self.last_network_time
                if time_diff > 0:
                    last_stats = self.last_network_stats[target]
                    sent_rate = (current_stats.bytes_sent - last_stats.bytes_sent) / time_diff
                    recv_rate = (current_stats.bytes_recv - last_stats.bytes_recv) / time_diff
                    total_rate = sent_rate + recv_rate
            
            # 更新上次统计
            self.last_network_stats[target] = current_stats
            self.last_network_time = current_time
            
            # 检查阈值
            warning_threshold = threshold.get('warning', 1000000)  # 默认1MB/s
            critical_threshold = threshold.get('critical', 5000000)  # 默认5MB/s
            
            is_normal = total_rate < warning_threshold
            level = 'normal'
            if total_rate >= critical_threshold:
                level = 'critical'
            elif total_rate >= warning_threshold:
                level = 'warning'
            
            return {
                'is_normal': is_normal,
                'value': round(total_rate, 2),
                'level': level,
                'message': f"网络速率: {self._bytes_to_mb(total_rate):.2f}MB/s (发送: {self._bytes_to_mb(sent_rate):.2f}MB/s, 接收: {self._bytes_to_mb(recv_rate):.2f}MB/s)",
                'details': {
                    'interface': target,
                    'sent_rate_bps': sent_rate,
                    'recv_rate_bps': recv_rate,
                    'total_rate_bps': total_rate,
                    'total_sent_bytes': current_stats.bytes_sent,
                    'total_recv_bytes': current_stats.bytes_recv,
                    'packets_sent': current_stats.packets_sent,
                    'packets_recv': current_stats.packets_recv
                }
            }
            
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"网络监控失败: {str(e)}"
            }
    
    def _bytes_to_gb(self, bytes_value: int) -> float:
        """字节转换为GB"""
        return bytes_value / (1024 ** 3)
    
    def _bytes_to_mb(self, bytes_value: float) -> float:
        """字节转换为MB"""
        return bytes_value / (1024 ** 2)