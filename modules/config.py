# config.py
"""
配置管理模块
负责监控配置和邮箱配置的增删改查操作
"""

import json
#import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from modules.database import execute_query, execute_single, execute_update, execute_insert

# 使用统一的日志配置
from modules.logger import logger

# 移除原有的 logging 配置
# 配置日志
#logging.basicConfig(level=logging.INFO)
#logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        pass
    
    def get_monitor_config(self, config_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取监控配置"""
        try:
            row = execute_single('SELECT * FROM monitor_configs WHERE id = ?', (config_id,))

            if row:
                config = dict(row)
                if config['threshold']:
                    try:
                        config['threshold'] = json.loads(config['threshold'])
                    except:
                        config['threshold'] = {}
                if config['extra_config']:
                    try:
                        config['extra_config'] = json.loads(config['extra_config'])
                    except:
                        config['extra_config'] = {}
                return config
            
            return None

        except Exception as e:
            logger.error(f"获取监控配置 {config_id} 失败: {e}")
            return None
        
    def get_all_monitor_configs(self) -> List[Dict[str, Any]]:
        """获取所有监控配置"""
        try:
            rows = execute_query('''
                SELECT * FROM monitor_configs 
                ORDER BY type, created_time
            ''')
            
            configs = []
            for row in rows:
                config = dict(row)
                # 解析JSON字段
                if config['threshold']:
                    try:
                        config['threshold'] = json.loads(config['threshold'])
                    except:
                        config['threshold'] = {}
                if config['extra_config']:
                    try:
                        config['extra_config'] = json.loads(config['extra_config'])
                    except:
                        config['extra_config'] = {}
                configs.append(config)
            
            return configs
        except Exception as e:
            logger.error(f"获取监控配置失败: {e}")
            return []
            
    def get_enabled_monitor_configs(self) -> List[Dict[str, Any]]:
        """获取所有启用的监控配置"""
        try:
            rows = execute_query('''
                SELECT * FROM monitor_configs 
                WHERE enabled = 1 
                ORDER BY type, created_time
            ''')
            
            configs = []
            for row in rows:
                config = dict(row)
                if config['threshold']:
                    try:
                        config['threshold'] = json.loads(config['threshold'])
                    except:
                        config['threshold'] = {}
                if config['extra_config']:
                    try:
                        config['extra_config'] = json.loads(config['extra_config'])
                    except:
                        config['extra_config'] = {}
                configs.append(config)
            
            return configs
        except Exception as e:
            logger.error(f"获取启用监控配置失败: {e}")
            return []      
    
    def create_monitor_config(self, config_data: Dict[str, Any]) -> Optional[int]:
        """创建监控配置"""
        try:
            # 处理JSON字段
            threshold = json.dumps(config_data.get('threshold', {})) if config_data.get('threshold') else None
            extra_config = json.dumps(config_data.get('extra_config', {})) if config_data.get('extra_config') else None
            
            config_id = execute_insert('''
                INSERT INTO monitor_configs 
                (name, type, target, enabled, interval_seconds, threshold, extra_config)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                config_data['name'],
                config_data['type'],
                config_data['target'],
                config_data.get('enabled', True),
                config_data.get('interval_seconds', 60),
                threshold,
                extra_config
            ))
            
            logger.info(f"创建监控配置成功: {config_data['name']} (ID: {config_id})")
            return config_id
        except Exception as e:
            logger.error(f"创建监控配置失败: {e}")
            return None        
    
    def update_monitor_config(self, config_id: int, config_data: Dict[str, Any]) -> bool:
        """更新监控配置"""
        try:
            # 构建更新字段和值
            update_fields = []
            update_values = []
            
            for field in ['name', 'type', 'target', 'enabled', 'interval_seconds']:
                if field in config_data:
                    update_fields.append(f"{field} = ?")
                    update_values.append(config_data[field])
            
            # 处理JSON字段
            if 'threshold' in config_data:
                update_fields.append("threshold = ?")
                update_values.append(json.dumps(config_data['threshold']) if config_data['threshold'] else None)
            
            if 'extra_config' in config_data:
                update_fields.append("extra_config = ?")
                update_values.append(json.dumps(config_data['extra_config']) if config_data['extra_config'] else None)
            
            # 添加更新时间
            update_fields.append("updated_time = ?")
            update_values.append(datetime.now().isoformat())
            
            # 添加配置ID
            update_values.append(config_id)
            
            if not update_fields:
                logger.warning("没有提供更新字段")
                return False

            query = f"UPDATE monitor_configs SET {', '.join(update_fields)} WHERE id = ?"
            success = execute_update(query, tuple(update_values))
            
            if success:
                logger.info(f"更新监控配置成功: ID {config_id}")
            else:
                logger.error(f"更新监控配置失败: ID {config_id}")
            
            return success
        except Exception as e:
            logger.error(f"更新监控配置 {config_id} 失败: {e}")
            return False
    
    def delete_monitor_config(self, config_id: int) -> bool:
        """删除监控配置"""
        try:
            success = execute_update('DELETE FROM monitor_configs WHERE id = ?', (config_id,))
            
            if success:
                logger.info(f"删除监控配置成功: ID {config_id}")
            else:
                logger.error(f"删除监控配置失败: ID {config_id}")
            
            return success
        except Exception as e:
            logger.error(f"删除监控配置 {config_id} 失败: {e}")
            return False
    
    def toggle_monitor_config(self, config_id: int, enabled: bool) -> bool:
        """启用/禁用监控配置"""
        try:
            success = execute_update('''
                UPDATE monitor_configs 
                SET enabled = ?, updated_time = ?
                WHERE id = ?
            ''', (enabled, datetime.now().isoformat(), config_id))
            
            if success:
                status = "启用" if enabled else "禁用"
                logger.info(f"{status}监控配置成功: ID {config_id}")
            else:
                logger.error(f"切换监控配置状态失败: ID {config_id}")
            
            return success
        except Exception as e:
            status = "启用" if enabled else "禁用"
            logger.error(f"{status}监控配置 {config_id} 失败: {e}")
            return False        
    
    # 邮箱配置管理方法
    
    def get_email_config(self) -> Optional[Dict[str, Any]]:
        """获取邮箱配置"""
        try:
            row = execute_single('SELECT * FROM email_config ORDER BY id DESC LIMIT 1')
            
            if row:
                config = dict(row)
                # 处理接收人列表
                if config['receivers']:
                    config['receivers_list'] = [r.strip() for r in config['receivers'].split(';')]
                return config
            
            return None
        except Exception as e:
            logger.error(f"获取邮箱配置失败: {e}")
            return None        
    
    def update_email_config(self, config_data: Dict[str, Any]) -> bool:
        """更新邮箱配置"""
        try:
            # 处理接收人列表
            receivers = config_data.get('receivers')
            if isinstance(receivers, list):
                receivers = ';'.join(receivers)
            
            # 检查是否已存在配置
            existing = execute_single('SELECT id FROM email_config ORDER BY id DESC LIMIT 1')
            
            if existing:
                # 更新现有配置
                success = execute_update('''
                    UPDATE email_config 
                    SET smtp_server = ?, smtp_port = ?, username = ?, password = ?,
                        sender = ?, receivers = ?, ssl_enabled = ?, updated_time = ?
                    WHERE id = ?
                ''', (
                    config_data['smtp_server'],
                    config_data['smtp_port'],
                    config_data['username'],
                    config_data['password'],
                    config_data['sender'],
                    receivers,
                    config_data.get('ssl_enabled', False),
                    datetime.now().isoformat(),
                    existing['id']
                ))
            else:
                # 插入新配置
                success = execute_update('''
                    INSERT INTO email_config 
                    (smtp_server, smtp_port, username, password, sender, receivers, ssl_enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    config_data['smtp_server'],
                    config_data['smtp_port'],
                    config_data['username'],
                    config_data['password'],
                    config_data['sender'],
                    receivers,
                    config_data.get('ssl_enabled', False)
                ))
            
            if success:
                logger.info("更新邮箱配置成功")
            else:
                logger.error("更新邮箱配置失败")
            
            return success
        except Exception as e:
            logger.error(f"更新邮箱配置失败: {e}")
            return False        
    
    # 工具方法
    
    def get_monitor_types(self) -> List[str]:
        """获取支持的监控类型"""
        return ['cpu', 'memory', 'disk', 'network', 'ssl', 'api', 'component']
    
    def get_default_thresholds(self, monitor_type: str) -> Dict[str, Any]:
        """获取默认阈值配置"""
        defaults = {
            'cpu': {'warning': 80, 'critical': 90},
            'memory': {'warning': 80, 'critical': 90},
            'disk': {'warning': 80, 'critical': 90},
            'network': {'warning': 1000000, 'critical': 5000000},  # 字节/秒
            'ssl': {'warning_days': 30, 'critical_days': 7},
            'api': {'expected_status': 200, 'timeout': 10},
            'component': {}  # 组件监控的阈值在extra_config中配置
        }
        return defaults.get(monitor_type, {})
    
    # 在 ConfigManager 类中添加以下方法

    def get_project_name(self) -> str:
        """获取项目名称"""
        try:
            row = execute_single('''
                SELECT config_value FROM system_config 
                WHERE config_key = 'project_name'
            ''')
            
            if row:
                return row['config_value']
            else:
                # 如果不存在，插入默认值
                self.update_project_name('xxx项目服务器')
                return 'xxx项目服务器'
                
        except Exception as e:
            logger.error(f"获取项目名称失败: {e}")
            return 'xxx项目服务器'        

    def update_project_name(self, project_name: str) -> bool:
        """更新项目名称"""
        try:
            success = execute_update('''
                INSERT OR REPLACE INTO system_config 
                (config_key, config_value, description, updated_time)
                VALUES (?, ?, ?, ?)
            ''', ('project_name', project_name, '项目名称', datetime.now().isoformat()))
            
            if success:
                logger.info(f"更新项目名称成功: {project_name}")
            else:
                logger.error(f"更新项目名称失败: {project_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"更新项目名称失败: {e}")
            return False        

    def get_system_config(self, config_key: str) -> Optional[str]:
        """获取系统配置值"""
        try:
            row = execute_single('''
                SELECT config_value FROM system_config 
                WHERE config_key = ?
            ''', (config_key,))
            
            return row['config_value'] if row else None
                
        except Exception as e:
            logger.error(f"获取系统配置失败 {config_key}: {e}")
            return None
    
    def update_system_config(self, config_key: str, config_value: str, description: str = None) -> bool:
        """更新系统配置"""
        try:
            if description is None:
                description = config_key
            
            success = execute_update('''
                INSERT OR REPLACE INTO system_config 
                (config_key, config_value, description, updated_time)
                VALUES (?, ?, ?, ?)
            ''', (config_key, config_value, description, datetime.now().isoformat()))
            
            if success:
                logger.info(f"更新系统配置成功: {config_key} = {config_value}")
            else:
                logger.error(f"更新系统配置失败: {config_key}")
            
            return success
            
        except Exception as e:
            logger.error(f"更新系统配置失败 {config_key}: {e}")
            return False
    
    """
    def get_project_name(self) -> str:
        #获取项目名称
        try:
            value = self.get_system_config('project_name')
            return value if value else 'xxx项目服务器'
        except:
            return 'xxx项目服务器'    
    """

    def get_data_retention_days(self) -> int:
        """获取数据保留天数"""
        try:
            value = self.get_system_config('data_retention_days')
            return int(value) if value else 30
        except:
            return 30
    
    def get_alert_retry_times(self) -> int:
        """获取报警重试次数"""
        try:
            value = self.get_system_config('alert_retry_times')
            return int(value) if value else 3
        except:
            return 3
    
    def get_max_alert_interval(self) -> int:
        """获取最大报警间隔"""
        try:
            value = self.get_system_config('max_alert_interval')
            return int(value) if value else 300
        except:
            return 300    