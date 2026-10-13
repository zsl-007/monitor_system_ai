# monitors/ssl.py
"""
SSL证书监控器 - 完整实现
支持多种SSL检查和错误处理
"""
try:
    # 使用绝对导入
    from monitors.base import BaseMonitor
except ImportError:
    # 备用导入方式
    import sys
    import os
    # 添加当前目录到路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from base import BaseMonitor

import socket
import ssl
import OpenSSL
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse

class SSLMonitor(BaseMonitor):
    """SSL证书监控器"""
    
    async def _check_impl(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查SSL证书过期时间 - 修复版本"""
        try:
            target = config['target']
            
            # 安全地获取阈值配置，避免 None 的情况
            threshold = config.get('threshold', {}) or {}  # 确保 threshold 不是 None
            warning_days = threshold.get('warning_days', 30)
            critical_days = threshold.get('critical_days', 7)
            
            # 安全地获取额外配置
            extra_config = config.get('extra_config', {}) or {}
            port = extra_config.get('port', 443)
            
            # 获取证书信息
            cert_info = await self._get_certificate_info(target, port)
            if not cert_info:
                return {
                    'is_normal': False,
                    'message': f"无法获取 {target}:{port} 的SSL证书信息，请检查域名和端口是否正确"
                }
            
            # 检查证书信息中是否包含必要的字段
            if 'days_remaining' not in cert_info or cert_info['days_remaining'] is None:
                return {
                    'is_normal': False,
                    'message': f"无法解析 {target} 的证书过期时间"
                }
            
            days_remaining = cert_info['days_remaining']
            expiry_date = cert_info.get('not_after', '未知')
            
            # 判断证书状态
            is_normal = days_remaining > warning_days
            level = 'normal'
            if days_remaining <= critical_days:
                level = 'critical'
                is_normal = False
            elif days_remaining <= warning_days:
                level = 'warning'
                is_normal = False
            
            status_message = f"SSL证书正常，{days_remaining}天后过期" if is_normal else f"SSL证书即将过期，剩余{days_remaining}天"
            
            return {
                'is_normal': is_normal,
                'value': days_remaining,
                'level': level,
                'message': f"{status_message} ({expiry_date})",
                'details': {
                    'domain': target,
                    'port': port,
                    'expiry_date': expiry_date,
                    'days_remaining': days_remaining,
                    'issuer': cert_info.get('issuer', 'Unknown'),
                    'subject': cert_info.get('subject', 'Unknown'),
                    'serial_number': cert_info.get('serial_number', 'Unknown'),
                    'signature_algorithm': cert_info.get('signature_algorithm', 'Unknown')
                }
            }
            
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"SSL证书检查失败: {str(e)}"
            }

    async def _get_certificate_info(self, domain: str, port: int = 443) -> Optional[Dict[str, Any]]:
        """获取SSL证书详细信息 - 修复版本"""
        try:
            # 验证输入参数
            if not domain or not isinstance(domain, str):
                return None
            
            # 方法1: 使用OpenSSL获取更详细的证书信息
            cert_info = await self._get_certificate_openssl(domain, port)
            if cert_info:
                return cert_info
            
            # 方法2: 回退到标准ssl库
            cert_info = await self._get_certificate_standard(domain, port)
            if cert_info:
                return cert_info
                
            return None
            
        except Exception as e:
            return None
        
    async def _get_certificate_openssl(self, domain: str, port: int) -> Optional[Dict[str, Any]]:
        """使用OpenSSL获取证书信息 - 修复版本"""
        try:
            # 创建SSL上下文
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # 连接到服务器
            with socket.create_connection((domain, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    # 获取证书的DER编码
                    der_cert = ssock.getpeercert(True)
                    
                    if der_cert:
                        # 使用OpenSSL解析证书
                        cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_ASN1, der_cert)
                        
                        # 获取证书过期时间
                        not_after = cert.get_notAfter()
                        if not not_after:
                            return None
                            
                        not_after_str = not_after.decode('ascii')
                        expiry_date = datetime.strptime(not_after_str, '%Y%m%d%H%M%SZ')
                        days_remaining = (expiry_date - datetime.now()).days
                        
                        # 获取颁发者
                        issuer = cert.get_issuer()
                        issuer_components = []
                        if issuer:
                            for k, v in issuer.get_components():
                                try:
                                    issuer_components.append(f"{k.decode()}={v.decode()}")
                                except:
                                    issuer_components.append(f"{k}={v}")
                        issuer_str = ", ".join(issuer_components) if issuer_components else "Unknown"
                        
                        # 获取主题
                        subject = cert.get_subject()
                        subject_components = []
                        if subject:
                            for k, v in subject.get_components():
                                try:
                                    subject_components.append(f"{k.decode()}={v.decode()}")
                                except:
                                    subject_components.append(f"{k}={v}")
                        subject_str = ", ".join(subject_components) if subject_components else "Unknown"
                        
                        return {
                            'not_after': expiry_date.strftime('%Y-%m-%d %H:%M:%S'),
                            'days_remaining': days_remaining,
                            'issuer': issuer_str,
                            'subject': subject_str,
                            'serial_number': str(cert.get_serial_number()) if cert.get_serial_number() else 'Unknown',
                            'signature_algorithm': cert.get_signature_algorithm().decode() if cert.get_signature_algorithm() else 'Unknown',
                            'version': cert.get_version()
                        }
            
            return None
            
        except Exception as e:
            return None
        
    async def _get_certificate_standard(self, domain: str, port: int) -> Optional[Dict[str, Any]]:
        """使用标准ssl库获取证书信息"""
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with socket.create_connection((domain, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    
                    if not cert:
                        return None
                    
                    # 解析证书过期时间
                    not_after = cert['notAfter']
                    expiry_date = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                    days_remaining = (expiry_date - datetime.now()).days
                    
                    # 解析主题
                    subject = {}
                    if 'subject' in cert:
                        for item in cert['subject']:
                            for key, value in item:
                                subject[key] = value
                    
                    # 解析颁发者
                    issuer = {}
                    if 'issuer' in cert:
                        for item in cert['issuer']:
                            for key, value in item:
                                issuer[key] = value
                    
                    return {
                        'not_after': expiry_date.strftime('%Y-%m-%d %H:%M:%S'),
                        'days_remaining': days_remaining,
                        'issuer': ", ".join([f"{k}={v}" for k, v in issuer.items()]),
                        'subject': ", ".join([f"{k}={v}" for k, v in subject.items()]),
                        'serial_number': 'N/A',
                        'signature_algorithm': 'N/A'
                    }
                    
        except Exception as e:
            return None