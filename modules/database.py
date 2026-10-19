# database.py
"""
数据库连接管理模块
提供统一的数据库连接池管理，支持连接复用和自动关闭
"""

import sqlite3
import threading
#import logging
import json
import os
from typing import Optional, Callable, Any
from contextlib import contextmanager
from datetime import datetime

# 使用统一的日志配置
from modules.logger import logger

# 移除原有的 logging 配置
# 配置日志
#logging.basicConfig(level=logging.INFO)
#logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库连接管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_manager()
            return cls._instance
    
    def _init_manager(self):
        """初始化数据库管理器"""
        self.db_path = "data/monitor_system.db"
        self.data_dir = "data"
        self._local = threading.local()
        self._connection_pool = []
        self.max_pool_size = 5
        logger.info("数据库连接管理器初始化完成")
    
    def ensure_data_dir(self):
        """确保数据目录存在"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            logger.info(f"创建数据目录: {self.data_dir}")
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        # 检查线程本地存储中是否有连接
        if hasattr(self._local, 'connection'):
            return self._local.connection
        
        # 从连接池获取或创建新连接
        if self._connection_pool:
            conn = self._connection_pool.pop()
            #logger.debug("从连接池获取数据库连接")
        else:
            conn = self._create_connection()
            #logger.debug("创建新的数据库连接")
        
        # 存储到线程本地
        self._local.connection = conn
        return conn
    
    def _create_connection(self) -> sqlite3.Connection:
        """创建新的数据库连接"""
        try:
            # 确保数据目录存在
            self.ensure_data_dir()
            
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            # 启用外键约束
            conn.execute("PRAGMA foreign_keys = ON")
            # 设置繁忙超时
            conn.execute("PRAGMA busy_timeout = 5000")
            return conn
        except sqlite3.Error as e:
            logger.error(f"创建数据库连接失败: {e}")
            raise
    
    def release_connection(self, conn: sqlite3.Connection):
        """释放数据库连接回连接池"""
        try:
            if hasattr(self._local, 'connection'):
                del self._local.connection
            
            # 如果连接池未满，回收连接；否则关闭
            if len(self._connection_pool) < self.max_pool_size:
                self._connection_pool.append(conn)
                #logger.debug("连接回收到连接池")
            else:
                conn.close()
                #logger.debug("连接池已满，关闭连接")
        except sqlite3.Error as e:
            logger.error(f"释放数据库连接失败: {e}")
            conn.close()
    
    def close_all_connections(self):
        """关闭所有数据库连接"""
        for conn in self._connection_pool:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        self._connection_pool.clear()
        logger.info("所有数据库连接已关闭")
    
    def initialize_database(self):
        """初始化数据库表结构和默认数据"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 检查是否需要初始化
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='monitor_configs'")
                if cursor.fetchone():
                    logger.info("数据库已存在，跳过初始化")
                    return True
                
                #logger.info("开始初始化数据库...")
                
                # 创建所有表结构
                self._create_tables(cursor)
                
                # 插入初始数据
                self._insert_initial_data(cursor)
                
                conn.commit()
                #logger.info("数据库初始化完成")
                return True
                
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            return False
    
    def _create_tables(self, cursor):
        """创建所有数据库表"""
        # 监控配置表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS monitor_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,                    -- 监控项名称
            type TEXT NOT NULL,                    -- 监控类型: cpu/memory/disk/network/ssl/api/component
            target TEXT NOT NULL,                  -- 监控目标: URL/域名/组件名等
            enabled BOOLEAN DEFAULT 1,             -- 是否启用
            interval_seconds INTEGER DEFAULT 60,   -- 监测间隔(秒)
            threshold TEXT,                        -- 报警阈值(JSON格式存储不同类型阈值)
            extra_config TEXT,                     -- 额外配置(JSON格式)
            created_time DATETIME DEFAULT (datetime('now', 'localtime')),
            updated_time DATETIME DEFAULT (datetime('now', 'localtime'))
        )
        ''')
        
        # 邮箱配置表（全局配置）
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            smtp_server TEXT NOT NULL,
            smtp_port INTEGER NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            sender TEXT NOT NULL,                  -- 发件人邮箱
            receivers TEXT NOT NULL,               -- 收件人邮箱列表(分号分隔)
            ssl_enabled BOOLEAN DEFAULT 0,
            created_time DATETIME DEFAULT (datetime('now', 'localtime')),
            updated_time DATETIME DEFAULT (datetime('now', 'localtime'))
        )
        ''')

        # Webhook 配置表（支持多个配置）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhook_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                secret TEXT DEFAULT '',
                enabled BOOLEAN DEFAULT 1,
                created_time DATETIME DEFAULT (datetime('now', 'localtime')),
                updated_time DATETIME DEFAULT (datetime('now', 'localtime'))
            )
        ''')

        # Webhook 推送记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhook_push_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                webhook_id INTEGER NOT NULL,
                webhook_name TEXT DEFAULT '',
                webhook_url TEXT DEFAULT '',
                success BOOLEAN DEFAULT 0,
                response_code INTEGER DEFAULT 0,
                error_message TEXT DEFAULT '',
                pushed_time DATETIME DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (alert_id) REFERENCES alert_data (id),
                FOREIGN KEY (webhook_id) REFERENCES webhook_config (id)
            )
        ''')

        # 为推送记录表创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_webhook_push_alert 
            ON webhook_push_records(alert_id)
        ''')
        
        # 监控数据表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS monitor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,            -- 监控配置ID
            monitor_type TEXT NOT NULL,            -- 监控类型
            value REAL,                            -- 监控数值(CPU使用率等)
            status TEXT,                           -- 状态描述(用于API/组件监控)
            is_normal BOOLEAN DEFAULT 1,           -- 是否正常
            details TEXT,                           -- 详情说明
            created_time DATETIME DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (config_id) REFERENCES monitor_configs (id)
        )
        ''')
        
        # 为监控数据表创建索引以提高查询性能
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_monitor_data_config_time 
        ON monitor_data(config_id, created_time)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_monitor_data_type_time 
        ON monitor_data(monitor_type, created_time)
        ''')
        
        # 报警记录表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,            -- 监控配置ID
            monitor_type TEXT NOT NULL,            -- 监控类型
            alert_message TEXT NOT NULL,           -- 报警信息
            alert_time DATETIME DEFAULT (datetime('now', 'localtime')),
            sent BOOLEAN DEFAULT 0,                -- 是否已发送邮件
            receiver TEXT,                         -- 接收人邮箱
            created_time DATETIME DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (config_id) REFERENCES monitor_configs (id)
        )
        ''')
        
        # 为报警记录表创建索引
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_alert_data_time 
        ON alert_data(alert_time)
        ''')
        
        # 系统配置表（用于存储其他系统配置）
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT UNIQUE NOT NULL,       -- 配置键
            config_value TEXT,                     -- 配置值
            description TEXT,                      -- 配置描述
            created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_time DATETIME DEFAULT (datetime('now', 'localtime'))
        )
        ''')
        
        # 用户表（新增）
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,           -- 用户名
            password_hash TEXT NOT NULL,             -- 密码哈希
            is_active BOOLEAN DEFAULT 1,             -- 是否激活
            created_time DATETIME DEFAULT (datetime('now', 'localtime')),
            updated_time DATETIME DEFAULT (datetime('now', 'localtime'))
        )
        ''')
        
        # 为用户名创建索引
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_users_username 
        ON users(username)
        ''')
        
        # JWT令牌黑名单表（用于登出）
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS token_blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,                     -- JWT令牌
            expires_at DATETIME NOT NULL,            -- 令牌过期时间
            created_time DATETIME DEFAULT (datetime('now', 'localtime'))
        )
        ''')
        
        # 为令牌创建索引
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_token_blacklist_token 
        ON token_blacklist(token)
        ''')

        logger.info("所有表结构创建完成")
    
    def _insert_initial_data(self, cursor):
        """插入初始数据"""
        # 插入默认的系统监控配置
        default_monitors = [
            # 系统资源监控
            ('CPU使用率', 'cpu', 'system', 0, 60, '{"warning": 80, "critical": 90}'),
            ('内存使用率', 'memory', 'system', 0, 60, '{"warning": 80, "critical": 90}'),
            ('磁盘使用率', 'disk', '/', 0, 300, '{"warning": 80, "critical": 90}'),
            ('网络流量', 'network', 'eth0', 0, 60, '{"warning": 1000000, "critical": 5000000}'),  # 字节/秒
            
            # SSL证书监控示例（需要用户自行配置具体域名）(28800为8小时)
            ('示例SSL监控', 'ssl', 'example.com', 0, 28800, '{"warning_days": 30, "critical_days": 7}'),
            
            # API监控示例
            ('示例API监控', 'api', 'https://www.baidu.com', 0, 60, '{"expected_status": 200, "timeout": 10}'),
            
            # 组件监控示例
            ('Redis服务', 'component', 'redis', 0, 300, '{"host": "127.0.0.1", "port": 6379}'),
            ('RabbitMQ服务', 'component', 'rabbitmq', 0, 300, '{"host": "127.0.0.1", "port": 5672, "username": "guest", "password": "guest"}')
        ]
        
        for name, monitor_type, target, enabled, interval, threshold in default_monitors:
            cursor.execute('''
            INSERT OR IGNORE INTO monitor_configs 
            (name, type, target, enabled, interval_seconds, threshold)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, monitor_type, target, enabled, interval, threshold))
        
        # 插入空的邮箱配置
        cursor.execute('''
        INSERT OR IGNORE INTO email_config 
        (smtp_server, smtp_port, username, password, sender, receivers, ssl_enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('smtp.example.com', 465, 'your_username', 'your_password', 'noreply@example.com', 'admin@example.com', 0))
        
        # 插入系统配置
        system_configs = [
            ('data_retention_days', '30', '监控数据保留天数'),
            ('alert_retry_times', '3', '报警重试次数'),
            ('max_alert_interval', '300', '最大报警间隔(秒)'),
            ('project_name', 'xxx项目服务器', '项目名称')
        ]
        
        for key, value, description in system_configs:
            cursor.execute('''
            INSERT OR IGNORE INTO system_config 
            (config_key, config_value, description)
            VALUES (?, ?, ?)
            ''', (key, value, description))
        
        # 插入默认用户（新增）
        import hashlib
        default_password = "xhx_jc@2025!"
        password_hash = hashlib.sha256(default_password.encode()).hexdigest()
        
        cursor.execute('''
        INSERT OR IGNORE INTO users 
        (username, password_hash, is_active)
        VALUES (?, ?, ?)
        ''', ('jc_admin', password_hash, 1))  # 明确设置 is_active = 1

        logger.info("初始数据插入完成")

# 创建全局数据库管理器实例
db_manager = DatabaseManager()

@contextmanager
def get_db_connection():
    """
    数据库连接上下文管理器
    自动管理连接的获取和释放
    """
    conn = None
    try:
        conn = db_manager.get_connection()
        yield conn
    except sqlite3.Error as e:
        logger.error(f"数据库操作失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            db_manager.release_connection(conn)

def execute_query(query: str, params: tuple = None) -> list:
    """执行查询并返回结果列表"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

def execute_single(query: str, params: tuple = None) -> Optional[dict]:
    """执行查询并返回单条结果"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        row = cursor.fetchone()
        return dict(row) if row else None

def execute_update(query: str, params: tuple = None) -> bool:
    """执行更新操作并返回是否成功"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return True
    except sqlite3.Error as e:
        logger.error(f"执行更新失败: {e}")
        return False

def execute_insert(query: str, params: tuple = None) -> Optional[int]:
    """执行插入操作并返回插入的ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"执行插入失败: {e}")
        return None

def check_database_health() -> dict:
    """检查数据库健康状态"""
    try:
        # 首先尝试初始化数据库
        if not db_manager.initialize_database():
            return {
                'status': 'unhealthy',
                'message': '数据库初始化失败',
                'details': {}
            }
        
        with get_db_connection() as conn:
            # 检查表是否存在
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN (
                    'monitor_configs', 'monitor_data', 'alert_data',
                    'email_config', 'system_config',
                    'webhook_config', 'webhook_push_records'
                )
            """)
            tables = [row['name'] for row in cursor.fetchall()]
            
            # 检查连接池状态
            pool_status = {
                'pool_size': len(db_manager._connection_pool),
                'max_pool_size': db_manager.max_pool_size,
                'available_tables': tables
            }
            
            return {
                'status': 'healthy',
                'message': '数据库连接正常',
                'details': pool_status
            }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'message': f'数据库连接异常: {str(e)}',
            'details': {}
        }

def initialize_database():
    """初始化数据库（供外部调用）"""
    return db_manager.initialize_database()