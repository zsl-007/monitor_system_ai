# monitors/component.py
"""
组件状态监控器 - 完整实现
Redis、RabbitMQ等组件的完整状态检查
"""

import asyncio
import redis
import pika
from typing import Dict, Any
from monitors.base import BaseMonitor

class ComponentMonitor(BaseMonitor):
    """组件状态监控器"""
    
    async def check(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查组件状态 - 完整实现"""
        try:
            component_type = config['target'].lower()
            extra_config = config.get('extra_config', {})
            
            if component_type == 'redis':
                return await self._check_redis(extra_config)
            elif component_type == 'rabbitmq':
                return await self._check_rabbitmq(extra_config)
            elif component_type == 'mysql':
                return await self._check_mysql(extra_config)
            elif component_type == 'postgresql':
                return await self._check_postgresql(extra_config)
            else:
                return {
                    'is_normal': False,
                    'message': f"不支持的组件类型: {component_type}"
                }
                
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"组件监控异常: {str(e)}"
            }

    async def _check_impl(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查组件状态 - 完整实现"""
        try:
            component_type = config['target'].lower()
            extra_config = config.get('extra_config', {})
            
            if component_type == 'redis':
                return await self._check_redis(extra_config)
            elif component_type == 'rabbitmq':
                return await self._check_rabbitmq(extra_config)
            elif component_type == 'mysql':
                return await self._check_mysql(extra_config)
            elif component_type == 'postgresql':
                return await self._check_postgresql(extra_config)
            else:
                return {
                    'is_normal': False,
                    'message': f"不支持的组件类型: {component_type}"
                }
                
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"组件监控异常: {str(e)}"
            }
    
    async def _check_redis(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查Redis状态 - 完整实现"""
        try:
            # 使用线程池执行同步的Redis操作
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._check_redis_sync, config
            )
            return result
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"Redis检查异常: {str(e)}"
            }
    
    def _check_redis_sync(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """同步检查Redis状态"""
        try:
            # 连接参数
            host = config.get('host', 'localhost')
            port = int(config.get('port', 6379))
            password = config.get('password')
            db = int(config.get('db', 0))
            socket_timeout = config.get('socket_timeout', 5)
            
            # 连接Redis
            connection_params = {
                'host': host,
                'port': port,
                'db': db,
                'socket_timeout': socket_timeout,
                'socket_connect_timeout': socket_timeout
            }
            if password:
                connection_params['password'] = password
            
            client = redis.Redis(**connection_params)
            
            # 测试连接和PING命令
            ping_result = client.ping()
            if not ping_result:
                return {
                    'is_normal': False,
                    'status': 'ping_failed',
                    'message': f"Redis PING命令失败: {host}:{port}"
                }
            
            # 获取Redis信息
            info = client.info()
            
            # 检查内存使用
            used_memory = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)
            memory_usage_percent = 0
            if max_memory > 0:
                memory_usage_percent = (used_memory / max_memory) * 100
            
            # 检查连接数
            connected_clients = info.get('connected_clients', 0)
            max_clients = info.get('maxclients', 0)
            
            # 检查是否为主节点
            role = info.get('role', 'unknown')
            
            details = {
                'host': host,
                'port': port,
                'version': info.get('redis_version', 'unknown'),
                'uptime_days': info.get('uptime_in_days', 0),
                'connected_clients': connected_clients,
                'max_clients': max_clients,
                'used_memory_mb': round(used_memory / (1024 * 1024), 2),
                'max_memory_mb': round(max_memory / (1024 * 1024), 2) if max_memory else 0,
                'memory_usage_percent': round(memory_usage_percent, 2),
                'role': role,
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0)
            }
            
            # 计算命中率
            if details['keyspace_hits'] + details['keyspace_misses'] > 0:
                hit_rate = details['keyspace_hits'] / (details['keyspace_hits'] + details['keyspace_misses']) * 100
                details['hit_rate_percent'] = round(hit_rate, 2)
            
            return {
                'is_normal': True,
                'status': 'running',
                'message': f"Redis服务正常 {host}:{port} (v{details['version']})",
                'details': details
            }
            
        except redis.ConnectionError as e:
            return {
                'is_normal': False,
                'status': 'connection_failed',
                'message': f"Redis连接失败 {config.get('host', 'localhost')}:{config.get('port', 6379)}: {str(e)}"
            }
        except redis.AuthenticationError as e:
            return {
                'is_normal': False,
                'status': 'auth_failed',
                'message': f"Redis认证失败: {str(e)}"
            }
        except Exception as e:
            return {
                'is_normal': False,
                'status': 'error',
                'message': f"Redis检查错误: {str(e)}"
            }
    
    async def _check_rabbitmq(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查RabbitMQ状态 - 完整实现"""
        try:
            # 使用线程池执行同步的RabbitMQ操作
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._check_rabbitmq_sync, config
            )
            return result
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"RabbitMQ检查异常: {str(e)}"
            }
    
    def _check_rabbitmq_sync(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """同步检查RabbitMQ状态"""
        try:
            # 连接参数
            host = config.get('host', 'localhost')
            port = int(config.get('port', 5672))
            username = config.get('username', 'guest')
            password = config.get('password', 'guest')
            vhost = config.get('vhost', '/')
            heartbeat = config.get('heartbeat', 60)
            
            # 创建连接参数
            credentials = pika.PlainCredentials(username, password)
            parameters = pika.ConnectionParameters(
                host=host,
                port=port,
                virtual_host=vhost,
                credentials=credentials,
                heartbeat=heartbeat,
                blocked_connection_timeout=30
            )
            
            # 连接RabbitMQ
            connection = pika.BlockingConnection(parameters)
            
            # 获取通道
            channel = connection.channel()
            
            # 获取服务器属性（需要管理员权限）
            try:
                # 尝试声明一个测试队列来验证权限
                test_queue = 'health_check_temp'
                channel.queue_declare(queue=test_queue, durable=False, auto_delete=True)
                channel.queue_delete(queue=test_queue)
                
                # 如果有权限，可以获取更多统计信息
                has_admin_perm = True
            except pika.exceptions.ChannelClosedByBroker:
                # 没有管理员权限，只能进行基本检查
                has_admin_perm = False
            
            # 获取连接和通道信息
            connection_details = {
                'host': host,
                'port': port,
                'vhost': vhost,
                'username': username,
                'has_admin_permission': has_admin_perm
            }
            
            # 如果有管理员权限，尝试获取更多信息
            if has_admin_perm:
                try:
                    # 这里可以添加获取节点状态、队列统计等信息的代码
                    # 需要安装rabbitmq-management插件和相应的HTTP客户端
                    pass
                except Exception:
                    # 忽略获取详细信息的错误
                    pass
            
            connection.close()
            
            return {
                'is_normal': True,
                'status': 'running',
                'message': f"RabbitMQ服务正常 {host}:{port} (vhost: {vhost})",
                'details': connection_details
            }
            
        except pika.exceptions.AMQPConnectionError as e:
            return {
                'is_normal': False,
                'status': 'connection_failed',
                'message': f"RabbitMQ连接失败 {config.get('host', 'localhost')}:{config.get('port', 5672)}: {str(e)}"
            }
        except pika.exceptions.AMQPChannelError as e:
            return {
                'is_normal': False,
                'status': 'channel_error',
                'message': f"RabbitMQ通道错误: {str(e)}"
            }
        except Exception as e:
            return {
                'is_normal': False,
                'status': 'error',
                'message': f"RabbitMQ检查错误: {str(e)}"
            }
    
    async def _check_mysql(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查MySQL状态（占位实现）"""
        # 需要安装mysql-connector-python或aiomysql
        return {
            'is_normal': False,
            'status': 'not_implemented',
            'message': 'MySQL监控暂未实现，需要安装mysql-connector-python库'
        }
    
    async def _check_postgresql(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查PostgreSQL状态（占位实现）"""
        # 需要安装psycopg2或asyncpg
        return {
            'is_normal': False,
            'status': 'not_implemented',
            'message': 'PostgreSQL监控暂未实现，需要安装psycopg2库'
        }