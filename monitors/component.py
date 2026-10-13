# monitors/component.py
"""
组件状态监控器 - 完整实现
Redis、RabbitMQ、MySQL、PostgreSQL、达梦DM、SQL Server等组件的完整状态检查
"""

import asyncio
import time
import os
import base64
from hashlib import sha256
from typing import Dict, Any

import redis
import pika
from monitors.base import BaseMonitor

# ---------- 数据库驱动按需导入 ----------

def _import_db_drivers():
    """按需导入数据库驱动，避免缺少驱动时启动失败"""
    drivers = {}
    try:
        import pymysql
        drivers['mysql'] = pymysql
    except ImportError:
        pass
    try:
        import psycopg2
        drivers['postgresql'] = psycopg2
    except ImportError:
        pass
    try:
        import dmPython
        drivers['dm'] = dmPython
    except ImportError:
        pass
    try:
        import pymssql
        drivers['sqlserver'] = pymssql
    except ImportError:
        pass
    return drivers

_DB_DRIVERS = _import_db_drivers()

# 数据库默认端口
DB_DEFAULT_PORTS = {
    'mysql': 3306,
    'postgresql': 5432,
    'dm': 5236,
    'sqlserver': 1433
}


# ---------- 密码安全存储 ----------

def _get_encryption_key() -> bytes:
    """获取加密密钥 — 优先环境变量，回退到 SECRET_KEY 派生"""
    key_env = os.getenv('DB_PASSWORD_ENCRYPTION_KEY')
    if key_env:
        return base64.urlsafe_b64encode(sha256(key_env.encode()).digest())
    try:
        from modules.auth import SECRET_KEY
        return base64.urlsafe_b64encode(sha256(SECRET_KEY.encode()).digest())
    except Exception:
        # 回退到固定密钥（仅用于无 auth 模块的场景）
        return base64.urlsafe_b64encode(sha256(b'monitor_system_ai_default_key').digest())


def _encrypt_password(plain: str) -> str:
    """加密密码 — 存储时调用"""
    if not plain or plain.startswith('enc:'):
        return plain  # 已加密或空密码
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_get_encryption_key())
        return f"enc:{f.encrypt(plain.encode()).decode()}"
    except Exception:
        # cryptography 库未安装时回退到明文
        return plain


def _decrypt_password(encrypted: str) -> str:
    """解密密码 — 读取时调用"""
    if not encrypted or not encrypted.startswith('enc:'):
        return encrypted  # 明文或空密码（向后兼容）
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_get_encryption_key())
        return f.decrypt(encrypted[4:].encode()).decode()
    except Exception:
        # 解密失败时返回空密码
        return ''


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
            elif component_type == 'dm':
                return await self._check_dm(extra_config)
            elif component_type == 'sqlserver':
                return await self._check_sqlserver(extra_config)
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
            elif component_type == 'dm':
                return await self._check_dm(extra_config)
            elif component_type == 'sqlserver':
                return await self._check_sqlserver(extra_config)
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
        """检查MySQL状态 - 完整实现"""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._check_mysql_sync, config
            )
            return result
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"MySQL检查异常: {str(e)}"
            }

    def _check_mysql_sync(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """同步检查MySQL状态"""
        if 'mysql' not in _DB_DRIVERS:
            return {
                'is_normal': False,
                'status': 'driver_missing',
                'message': 'MySQL驱动未安装，请安装pymysql库: pip install pymysql'
            }

        host = config.get('host', 'localhost')
        port = int(config.get('port', 3306))
        username = config.get('username', 'root')
        password = _decrypt_password(config.get('password', ''))
        database = config.get('database', '')
        socket_timeout = int(config.get('socket_timeout', 5))

        start_time = time.time()

        try:
            pymysql = _DB_DRIVERS['mysql']
            conn = pymysql.connect(
                host=host, port=port, user=username,
                password=password, database=database,
                connect_timeout=socket_timeout
            )

            response_time = round(time.time() - start_time, 3)
            cursor = conn.cursor()

            # 获取版本
            cursor.execute('SELECT VERSION()')
            row = cursor.fetchone()
            version = str(row[0]) if row else 'unknown'

            # 获取连接数
            connections = 0
            max_connections = 0
            try:
                cursor.execute('SHOW STATUS LIKE "Threads_connected"')
                row = cursor.fetchone()
                if row and len(row) > 1:
                    connections = int(row[1])
            except Exception:
                pass
            try:
                cursor.execute('SHOW VARIABLES LIKE "max_connections"')
                row = cursor.fetchone()
                if row and len(row) > 1:
                    max_connections = int(row[1])
            except Exception:
                pass

            cursor.close()
            conn.close()

            details = {
                'host': host,
                'port': port,
                'database': database,
                'db_type': 'mysql',
                'version': version,
                'response_time': response_time,
                'connections': connections,
                'max_connections': max_connections
            }

            return {
                'is_normal': True,
                'status': 'running',
                'message': f"MySQL服务正常 {host}:{port}/{database} (v{version})",
                'details': details
            }

        except Exception as e:
            response_time = round(time.time() - start_time, 3)
            return {
                'is_normal': False,
                'status': 'connection_failed',
                'message': f"MySQL连接失败 {host}:{port}: {str(e)}",
                'details': {'response_time': response_time}
            }

    async def _check_postgresql(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查PostgreSQL状态 - 完整实现"""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._check_postgresql_sync, config
            )
            return result
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"PostgreSQL检查异常: {str(e)}"
            }

    def _check_postgresql_sync(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """同步检查PostgreSQL状态"""
        if 'postgresql' not in _DB_DRIVERS:
            return {
                'is_normal': False,
                'status': 'driver_missing',
                'message': 'PostgreSQL驱动未安装，请安装psycopg2库: pip install psycopg2-binary'
            }

        host = config.get('host', 'localhost')
        port = int(config.get('port', 5432))
        username = config.get('username', 'postgres')
        password = _decrypt_password(config.get('password', ''))
        database = config.get('database', '')
        socket_timeout = int(config.get('socket_timeout', 5))

        start_time = time.time()

        try:
            psycopg2 = _DB_DRIVERS['postgresql']
            conn = psycopg2.connect(
                host=host, port=port, user=username,
                password=password, dbname=database,
                connect_timeout=socket_timeout
            )

            response_time = round(time.time() - start_time, 3)
            cursor = conn.cursor()

            # 获取版本
            cursor.execute('SELECT version()')
            row = cursor.fetchone()
            version = str(row[0]) if row else 'unknown'

            # 获取连接数
            connections = 0
            max_connections = 0
            try:
                cursor.execute('SELECT count(*) FROM pg_stat_activity')
                row = cursor.fetchone()
                if row:
                    connections = int(row[0])
            except Exception:
                pass
            try:
                cursor.execute('SHOW max_connections')
                row = cursor.fetchone()
                if row:
                    max_connections = int(row[0])
            except Exception:
                pass

            cursor.close()
            conn.close()

            details = {
                'host': host,
                'port': port,
                'database': database,
                'db_type': 'postgresql',
                'version': version,
                'response_time': response_time,
                'connections': connections,
                'max_connections': max_connections
            }

            return {
                'is_normal': True,
                'status': 'running',
                'message': f"PostgreSQL服务正常 {host}:{port}/{database} (v{version})",
                'details': details
            }

        except Exception as e:
            response_time = round(time.time() - start_time, 3)
            return {
                'is_normal': False,
                'status': 'connection_failed',
                'message': f"PostgreSQL连接失败 {host}:{port}: {str(e)}",
                'details': {'response_time': response_time}
            }

    async def _check_dm(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查达梦DM数据库状态 - 完整实现"""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._check_dm_sync, config
            )
            return result
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"达梦DM检查异常: {str(e)}"
            }

    def _check_dm_sync(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """同步检查达梦DM数据库状态"""
        if 'dm' not in _DB_DRIVERS:
            return {
                'is_normal': False,
                'status': 'driver_missing',
                'message': '达梦DM驱动未安装，请安装dmPython库（从达梦官方获取）'
            }

        host = config.get('host', 'localhost')
        port = int(config.get('port', 5236))
        username = config.get('username', 'SYSDBA')
        password = _decrypt_password(config.get('password', ''))
        database = config.get('database', '')
        socket_timeout = int(config.get('socket_timeout', 5))

        start_time = time.time()

        try:
            dmPython = _DB_DRIVERS['dm']
            conn = dmPython.connect(
                user=username, password=password,
                server=host, port=port
            )

            response_time = round(time.time() - start_time, 3)
            cursor = conn.cursor()

            # 获取版本
            version = 'unknown'
            try:
                cursor.execute('SELECT banner FROM v$version')
                row = cursor.fetchone()
                if row:
                    version = str(row[0])
            except Exception:
                pass

            cursor.close()
            conn.close()

            details = {
                'host': host,
                'port': port,
                'database': database,
                'db_type': 'dm',
                'version': version,
                'response_time': response_time
            }

            return {
                'is_normal': True,
                'status': 'running',
                'message': f"达梦DM数据库正常 {host}:{port} (v{version})",
                'details': details
            }

        except Exception as e:
            response_time = round(time.time() - start_time, 3)
            return {
                'is_normal': False,
                'status': 'connection_failed',
                'message': f"达梦DM数据库连接失败 {host}:{port}: {str(e)}",
                'details': {'response_time': response_time}
            }

    async def _check_sqlserver(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查SQL Server状态 - 完整实现"""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._check_sqlserver_sync, config
            )
            return result
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"SQL Server检查异常: {str(e)}"
            }

    def _check_sqlserver_sync(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """同步检查SQL Server状态"""
        if 'sqlserver' not in _DB_DRIVERS:
            return {
                'is_normal': False,
                'status': 'driver_missing',
                'message': 'SQL Server驱动未安装，请安装pymssql库: pip install pymssql'
            }

        host = config.get('host', 'localhost')
        port = int(config.get('port', 1433))
        username = config.get('username', 'sa')
        password = _decrypt_password(config.get('password', ''))
        database = config.get('database', '')
        socket_timeout = int(config.get('socket_timeout', 5))

        start_time = time.time()

        try:
            pymssql = _DB_DRIVERS['sqlserver']
            conn = pymssql.connect(
                host=host, port=port, user=username,
                password=password, database=database,
                timeout=socket_timeout
            )

            response_time = round(time.time() - start_time, 3)
            cursor = conn.cursor()

            # 获取版本
            version = 'unknown'
            try:
                cursor.execute('SELECT @@VERSION')
                row = cursor.fetchone()
                if row:
                    version = str(row[0])
            except Exception:
                pass

            # 获取连接数
            connections = 0
            try:
                cursor.execute('SELECT @@CONNECTIONS')
                row = cursor.fetchone()
                if row and row[0]:
                    connections = int(row[0])
            except Exception:
                pass

            cursor.close()
            conn.close()

            details = {
                'host': host,
                'port': port,
                'database': database,
                'db_type': 'sqlserver',
                'version': version,
                'response_time': response_time,
                'connections': connections
            }

            return {
                'is_normal': True,
                'status': 'running',
                'message': f"SQL Server服务正常 {host}:{port}/{database} (v{version})",
                'details': details
            }

        except Exception as e:
            response_time = round(time.time() - start_time, 3)
            return {
                'is_normal': False,
                'status': 'connection_failed',
                'message': f"SQL Server连接失败 {host}:{port}: {str(e)}",
                'details': {'response_time': response_time}
            }