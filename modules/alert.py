# alert.py
"""
报警处理模块
负责监控结果的阈值判断、报警触发和邮件发送
"""

#import logging
import smtplib
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from modules.database import execute_query, execute_single, execute_update, execute_insert  # 新增导入

from modules.config import ConfigManager
config_manager = ConfigManager()    

# 使用统一的日志配置
from modules.logger import logger

# 移除原有的 logging 配置
# 配置日志
#logging.basicConfig(level=logging.INFO)
#logger = logging.getLogger(__name__)

@dataclass
class AlertRecord:
    """报警记录数据类"""
    config_id: int
    monitor_type: str
    alert_message: str
    alert_time: datetime
    sent: bool = False
    receiver: str = ""

class AlertManager:
    """报警管理器"""
    
    def __init__(self):
        self.email_config = None
        self._load_email_config()
        
        # 报警去重缓存，避免重复报警
        self.alert_cache = {}
        self.cache_ttl = 300  # 5分钟内相同报警不重复发送
        
    def _load_email_config(self):
        """加载邮箱配置"""
        try:
            row = execute_single('SELECT * FROM email_config ORDER BY id DESC LIMIT 1')
            
            if row:
                self.email_config = dict(row)
                # 处理接收人列表
                if self.email_config['receivers']:
                    self.email_config['receivers_list'] = [
                        r.strip() for r in self.email_config['receivers'].split(';')
                    ]
                logger.info("邮箱配置加载成功")
            else:
                logger.warning("未找到邮箱配置")
                
        except Exception as e:
            logger.error(f"加载邮箱配置失败: {e}")        
    
    def check_threshold(self, config: Dict[str, Any], result: Dict[str, Any]) -> Optional[AlertRecord]:
        """
        检查监控结果是否触发报警阈值
        
        Args:
            config: 监控配置
            result: 监控结果
            
        Returns:
            如果需要报警则返回AlertRecord，否则返回None
        """
        try:
            monitor_type = config['type']
            threshold = config.get('threshold', {})
            
            # 如果监控结果本身就不正常，直接报警（适用于API、组件监控）
            if not result.get('is_normal', True):
                return self._create_alert_record(config, result, "状态异常")
            
            # 根据监控类型进行阈值判断
            if monitor_type in ['cpu', 'memory', 'disk']:
                return self._check_system_threshold(config, result, threshold)
            elif monitor_type == 'network':
                return self._check_network_threshold(config, result, threshold)
            elif monitor_type == 'ssl':
                return self._check_ssl_threshold(config, result, threshold)
            else:
                # 其他类型（api、component）已经在上面处理了
                return None
                
        except Exception as e:
            logger.error(f"阈值检查失败 {config.get('name', 'Unknown')}: {e}")
            return None
    
    def _check_system_threshold(self, config: Dict[str, Any], result: Dict[str, Any], threshold: Dict[str, Any]) -> Optional[AlertRecord]:
        """检查系统资源阈值"""
        value = result.get('value', 0)
        warning = threshold.get('warning', 80)
        critical = threshold.get('critical', 90)
        
        if value >= critical:
            return self._create_alert_record(
                config, result, 
                f"严重异常: {value}% >= {critical}%", 
                'critical'
            )
        elif value >= warning:
            return self._create_alert_record(
                config, result, 
                f"警告: {value}% >= {warning}%", 
                'warning'
            )
        
        return None
    
    def _check_network_threshold(self, config: Dict[str, Any], result: Dict[str, Any], threshold: Dict[str, Any]) -> Optional[AlertRecord]:
        """检查网络流量阈值"""
        value = result.get('value', 0)
        warning = threshold.get('warning', 1000000)  # 1MB/s
        critical = threshold.get('critical', 5000000)  # 5MB/s
        
        if value >= critical:
            return self._create_alert_record(
                config, result, 
                f"网络流量严重异常: {self._bytes_to_mb(value):.2f}MB/s >= {self._bytes_to_mb(critical):.2f}MB/s", 
                'critical'
            )
        elif value >= warning:
            return self._create_alert_record(
                config, result, 
                f"网络流量警告: {self._bytes_to_mb(value):.2f}MB/s >= {self._bytes_to_mb(warning):.2f}MB/s", 
                'warning'
            )
        
        return None
    
    def _check_ssl_threshold(self, config: Dict[str, Any], result: Dict[str, Any], threshold: Dict[str, Any]) -> Optional[AlertRecord]:
        """检查SSL证书阈值"""
        days_remaining = result.get('value', 0)
        warning_days = threshold.get('warning_days', 30)
        critical_days = threshold.get('critical_days', 7)
        
        if days_remaining <= critical_days:
            return self._create_alert_record(
                config, result, 
                f"SSL证书严重警告: 剩余{days_remaining}天 <= {critical_days}天", 
                'critical'
            )
        elif days_remaining <= warning_days:
            return self._create_alert_record(
                config, result, 
                f"SSL证书警告: 剩余{days_remaining}天 <= {warning_days}天", 
                'warning'
            )
        
        return None
    
    def _create_alert_record(self, config: Dict[str, Any], result: Dict[str, Any], 
                           alert_message: str, level: str = 'warning') -> AlertRecord:
        """创建报警记录"""
        full_message = f"[{level.upper()}] {config['name']} - {alert_message}"
        
        # 添加详细信息
        if 'message' in result:
            full_message += f" | {result['message']}"
        
        return AlertRecord(
            config_id=config['id'],
            monitor_type=config['type'],
            alert_message=full_message,
            alert_time=datetime.now()
        )
    
    def should_send_alert(self, alert_record: AlertRecord) -> bool:
        """
        判断是否应该发送报警（基于去重逻辑）
        
        Args:
            alert_record: 报警记录
            
        Returns:
            是否应该发送报警
        """
        try:
            cache_key = f"{alert_record.config_id}_{alert_record.monitor_type}"
            current_time = datetime.now()
            
            # 检查缓存中是否有相同报警
            if cache_key in self.alert_cache:
                last_alert_time = self.alert_cache[cache_key]
                time_diff = (current_time - last_alert_time).total_seconds()
                
                # 如果在TTL时间内，不重复发送
                if time_diff < self.cache_ttl:
                    logger.debug(f"报警去重: {alert_record.alert_message}")
                    return False
            
            # 更新缓存
            self.alert_cache[cache_key] = current_time
            
            # 清理过期缓存
            self._clean_alert_cache()
            
            return True
            
        except Exception as e:
            logger.error(f"报警去重检查失败: {e}")
            return True
    
    def _clean_alert_cache(self):
        """清理过期的报警缓存"""
        try:
            current_time = datetime.now()
            expired_keys = []
            
            for key, alert_time in self.alert_cache.items():
                time_diff = (current_time - alert_time).total_seconds()
                if time_diff > self.cache_ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.alert_cache[key]
                
        except Exception as e:
            logger.error(f"清理报警缓存失败: {e}")
    
    # 在 AlertManager 类中添加获取项目名称的方法
    """
    def get_project_name(self) -> str:
        #获取项目名称
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT config_value FROM system_config 
                WHERE config_key = 'project_name'
            ''')
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return row[0]
            else:
                return '服务器监控系统'
                
        except Exception as e:
            logger.error(f"获取项目名称失败: {e}")
            return '服务器监控系统'
    """

    # 修改邮件主题
    async def send_alert_email(self, alert_record: AlertRecord) -> bool:
        """发送报警邮件"""
        if not self.email_config:
            logger.error("无法发送邮件：未配置邮箱信息")
            return False
        
        try:
            # 检查是否应该发送（去重）
            if not self.should_send_alert(alert_record):
                return True  # 认为是"成功"，因为是有意不发送 

            project_name = config_manager.get_project_name() #project_name = self.get_project_name()
            
            # 构建邮件内容
            subject = f"{project_name}报警 - {alert_record.alert_time.strftime('%Y-%m-%d %H:%M:%S')}"
            body = self._build_email_content(alert_record)
            
            # 发送邮件
            success = await self._send_email(subject, body)
            
            if success:
                alert_record.sent = True
                alert_record.receiver = self.email_config.get('receivers', '')
                logger.info(f"报警邮件发送成功: {alert_record.alert_message}")
            else:
                logger.error(f"报警邮件发送失败: {alert_record.alert_message}")
            
            return success
            
        except Exception as e:
            logger.error(f"发送报警邮件异常: {e}")
            return False
    
    # 修改邮件构建方法
    def _build_email_content(self, alert_record: AlertRecord) -> str:
        """构建邮件内容"""
        project_name = config_manager.get_project_name()#project_name = self.get_project_name()
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .alert {{ border-left: 4px solid #ff6b6b; padding: 15px; background: #fff5f5; margin: 15px 0; }}
                .info {{ margin: 10px 0; }}
                .time {{ color: #666; font-size: 14px; }}
                .footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚨 {project_name} - 报警通知</h1>
                <p>系统检测到异常情况，请及时处理</p>
            </div>
            
            <div class="alert">
                <h3>{alert_record.alert_message}</h3>
            </div>
            
            <div class="info">
                <p><strong>项目名称:</strong> {project_name}</p>
                <p><strong>报警时间:</strong> {alert_record.alert_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>监控类型:</strong> {alert_record.monitor_type}</p>
                <p><strong>配置ID:</strong> {alert_record.config_id}</p>
            </div>
            
            <div class="footer">
                <p>此邮件由 {project_name} 自动发送，请勿回复。</p>
                <p>如有疑问，请联系系统管理员。</p>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    async def _send_email(self, subject: str, body: str) -> bool:
        """实际发送邮件"""
        try:
            # 由于smtplib是同步的，我们在线程池中执行
            import asyncio
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._send_email_sync, subject, body
            )
            return result
            
        except Exception as e:
            logger.error(f"发送邮件异常: {e}")
            return False
    
    def _send_email_sync(self, subject: str, body: str) -> bool:
        """同步发送邮件"""
        try:
            config = self.email_config
            if not config:
                return False
            logger.debug(config)
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = config['sender']
            msg['To'] = config['receivers']
            msg['Subject'] = subject
            
            # 添加HTML内容
            msg.attach(MIMEText(body, 'html'))
            
            # 连接SMTP服务器
            if config.get('ssl_enabled'):
                server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'])
            else:
                server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
                # 启动TLS（如果支持）
                server.starttls()
            
            # 登录
            server.login(config['username'], config['password'])
            
            # 发送邮件
            receivers = [r.strip() for r in config['receivers'].split(';')]
            server.sendmail(config['sender'], receivers, msg.as_string())
            
            # 关闭连接
            server.quit()
            
            return True
            
        except smtplib.SMTPException as e:
            logger.error(f"SMTP错误: {e}")
            return False
        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
            return False
    
    def save_alert_record(self, alert_record: AlertRecord) -> bool:
        """
        保存报警记录到数据库
        
        Args:
            alert_record: 报警记录
            
        Returns:
            保存是否成功
        """
        try:
            execute_insert('''
                INSERT INTO alert_data 
                (config_id, monitor_type, alert_message, alert_time, sent, receiver)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                alert_record.config_id,
                alert_record.monitor_type,
                alert_record.alert_message,
                alert_record.alert_time,
                alert_record.sent,
                alert_record.receiver
            ))
            
            logger.debug(f"报警记录保存成功: {alert_record.alert_message}")
            return True
            
        except Exception as e:
            logger.error(f"保存报警记录失败: {e}")
            return False        
    
    def get_recent_alerts(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取最近的报警记录
        
        Args:
            hours: 查询最近多少小时的数据
            limit: 返回记录数量限制
            
        Returns:
            报警记录列表
        """
        try:
            start_time = datetime.now() - timedelta(hours=hours)
            
            rows = execute_query('''
                SELECT ad.*, mc.name as config_name 
                FROM alert_data ad
                LEFT JOIN monitor_configs mc ON ad.config_id = mc.id
                WHERE ad.alert_time >= ?
                ORDER BY ad.alert_time DESC
                LIMIT ?
            ''', (start_time, limit))
            
            alerts = []
            for row in rows:
                alerts.append(dict(row))
            
            return alerts
            
        except Exception as e:
            logger.error(f"获取报警记录失败: {e}")
            return []        
    
    def _bytes_to_mb(self, bytes_value: float) -> float:
        """字节转换为MB"""
        return bytes_value / (1024 ** 2)
		
    # 在 alert.py 的 AlertManager 类中添加

    async def send_test_email(self, subject: str, body: str, receivers: List[str] = None) -> bool:
        """
        发送测试邮件
        
        Args:
            subject: 邮件主题
            body: 邮件内容
            receivers: 收件人列表，如果为None则使用配置中的收件人
            
        Returns:
            发送是否成功
        """
        if not self.email_config:
            logger.error("无法发送测试邮件：未配置邮箱信息")
            return False
        
        try:
            # 使用指定的收件人或配置中的收件人
            if receivers:
                original_receivers = self.email_config['receivers']
                self.email_config['receivers'] = ';'.join(receivers)
            
            success = await self._send_email(subject, body)
            
            # 恢复原始收件人配置
            if receivers:
                self.email_config['receivers'] = original_receivers
                
            return success
            
        except Exception as e:
            logger.error(f"发送测试邮件失败: {e}")
            return False

    # 同样更新测试邮件发送方法
    def _build_test_email_content(self, config_info: Dict[str, Any]) -> str:
        """构建测试邮件内容"""
        project_name = config_manager.get_project_name()#project_name = self.get_project_name()
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; }}
                .content {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .config-details {{ background: white; padding: 15px; border-radius: 5px; border-left: 4px solid #28a745; }}
                .footer {{ color: #6c757d; font-size: 14px; text-align: center; margin-top: 30px; }}
                .success-badge {{ background: #28a745; color: white; padding: 5px 10px; border-radius: 15px; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>✅ {project_name} - 邮箱测试</h1>
                <p>邮箱配置验证成功</p>
            </div>
            
            <div class="content">
                <p>恭喜！您的{project_name}邮箱配置正确，可以正常发送报警邮件。</p>
                
                <div class="config-details">
                    <h3>配置详情</h3>
                    <p><strong>项目名称:</strong> {project_name}</p>
                    <p><strong>测试时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p><strong>SMTP服务器:</strong> {config_info.get('smtp_server', 'N/A')}</p>
                    <p><strong>SMTP端口:</strong> {config_info.get('smtp_port', 'N/A')}</p>
                    <p><strong>发件人:</strong> {config_info.get('sender', 'N/A')}</p>
                    <p><strong>收件人:</strong> {config_info.get('receivers', 'N/A')}</p>
                    <p><strong>SSL/TLS:</strong> {'已启用' if config_info.get('ssl_enabled') else '未启用'}</p>
                </div>
                
                <div style="text-align: center; margin: 20px 0;">
                    <span class="success-badge">测试通过</span>
                </div>
            </div>
            
            <div class="footer">
                <p>此邮件由 {project_name} 自动发送，用于验证邮箱配置。</p>
                <p>如果您未进行此测试，请检查系统安全性。</p>
            </div>
        </body>
        </html>
        """
        
        return html_content
