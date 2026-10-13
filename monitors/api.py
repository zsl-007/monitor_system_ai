# monitors/api.py
"""
API接口监控器 - 完整实现
支持多种HTTP方法、认证、超时设置和响应验证
"""

import aiohttp
import asyncio
import json
from typing import Dict, Any, Optional
from monitors.base import BaseMonitor

class APIMonitor(BaseMonitor):
    """API接口监控器"""
    
    async def check(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查API接口状态 - 完整实现"""
        try:
            url = config['target']
            extra_config = config.get('extra_config', {})
            threshold = config.get('threshold', {})
            
            # 获取配置参数
            method = extra_config.get('method', 'GET').upper()
            headers = extra_config.get('headers', {})
            body = extra_config.get('body')
            timeout = threshold.get('timeout', 10)
            expected_status = threshold.get('expected_status', 200)
            expected_keyword = threshold.get('expected_keyword')
            max_response_time = threshold.get('max_response_time', 5)  # 最大响应时间(秒)
            
            # 处理请求体
            json_data = None
            if body and method in ['POST', 'PUT', 'PATCH']:
                try:
                    json_data = json.loads(body) if isinstance(body, str) else body
                except json.JSONDecodeError:
                    json_data = body
            
            # 执行请求
            result = await self._make_request(
                url=url,
                method=method,
                headers=headers,
                json_data=json_data,
                timeout=timeout,
                expected_status=expected_status,
                expected_keyword=expected_keyword,
                max_response_time=max_response_time
            )
            
            return result
            
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"API监控异常: {str(e)}"
            }
    
    async def _make_request(self, 
                          url: str, 
                          method: str, 
                          headers: Dict[str, str],
                          json_data: Any,
                          timeout: int,
                          expected_status: int,
                          expected_keyword: Optional[str],
                          max_response_time: float) -> Dict[str, Any]:
        """执行HTTP请求并验证响应"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                request_params = {
                    'url': url,
                    'method': method,
                    'headers': headers,
                    'ssl': False  # 跳过SSL验证以兼容自签名证书
                }
                
                if json_data and method in ['POST', 'PUT', 'PATCH']:
                    request_params['json'] = json_data
                
                async with session.request(**request_params) as response:
                    response_time = asyncio.get_event_loop().time() - start_time
                    
                    # 读取响应内容
                    response_text = await response.text()
                    
                    # 检查状态码
                    status_ok = response.status == expected_status
                    
                    # 检查关键字
                    keyword_ok = True
                    if expected_keyword:
                        keyword_ok = expected_keyword in response_text
                    
                    # 检查响应时间
                    response_time_ok = response_time <= max_response_time
                    
                    # 综合判断
                    is_normal = status_ok and keyword_ok and response_time_ok
                    
                    # 构建消息
                    message_parts = []
                    if not status_ok:
                        message_parts.append(f"状态码: {response.status} (期望: {expected_status})")
                    if not keyword_ok:
                        message_parts.append(f"未找到关键字: {expected_keyword}")
                    if not response_time_ok:
                        message_parts.append(f"响应时间: {response_time:.2f}s (超时: {max_response_time}s)")
                    
                    message = "API检查正常" if is_normal else f"API异常: {'; '.join(message_parts)}"
                    
                    # 构建详细信息
                    details = {
                        'url': url,
                        'method': method,
                        'actual_status': response.status,
                        'expected_status': expected_status,
                        'response_time': round(response_time, 3),
                        'max_response_time': max_response_time,
                        'response_size': len(response_text),
                        'has_expected_keyword': keyword_ok if expected_keyword else None,
                        'headers': dict(response.headers)
                    }
                    
                    # 如果是错误响应，包含部分响应内容
                    if not is_normal and response_text:
                        # 只截取前200个字符避免数据过大
                        details['response_preview'] = response_text[:200] + ('...' if len(response_text) > 200 else '')
                    
                    return {
                        'is_normal': is_normal,
                        'value': response.status,
                        'response_time': response_time,
                        'message': message,
                        'details': details
                    }
                        
        except asyncio.TimeoutError:
            response_time = asyncio.get_event_loop().time() - start_time
            return {
                'is_normal': False,
                'response_time': response_time,
                'message': f"API请求超时: {timeout}秒"
            }
        except aiohttp.ClientError as e:
            response_time = asyncio.get_event_loop().time() - start_time
            return {
                'is_normal': False,
                'response_time': response_time,
                'message': f"API请求失败: {str(e)}"
            }
        except Exception as e:
            response_time = asyncio.get_event_loop().time() - start_time
            return {
                'is_normal': False,
                'response_time': response_time,
                'message': f"API请求异常: {str(e)}"
            }
        
    async def _check_impl(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """检查API接口状态 - 完整实现"""
        try:
            url = config['target']
            extra_config = config.get('extra_config', {})
            threshold = config.get('threshold', {})
            
            # 获取配置参数
            method = extra_config.get('method', 'GET').upper()
            headers = extra_config.get('headers', {})
            body = extra_config.get('body')
            timeout = threshold.get('timeout', 10)
            expected_status = threshold.get('expected_status', 200)
            expected_keyword = threshold.get('expected_keyword')
            max_response_time = threshold.get('max_response_time', 5)  # 最大响应时间(秒)
            
            # 处理请求体
            json_data = None
            if body and method in ['POST', 'PUT', 'PATCH']:
                try:
                    json_data = json.loads(body) if isinstance(body, str) else body
                except json.JSONDecodeError:
                    json_data = body
            
            # 执行请求
            result = await self._make_request(
                url=url,
                method=method,
                headers=headers,
                json_data=json_data,
                timeout=timeout,
                expected_status=expected_status,
                expected_keyword=expected_keyword,
                max_response_time=max_response_time
            )
            
            return result
            
        except Exception as e:
            return {
                'is_normal': False,
                'message': f"API监控异常: {str(e)}"
            }
    
    async def _make_request(self, 
                          url: str, 
                          method: str, 
                          headers: Dict[str, str],
                          json_data: Any,
                          timeout: int,
                          expected_status: int,
                          expected_keyword: Optional[str],
                          max_response_time: float) -> Dict[str, Any]:
        """执行HTTP请求并验证响应"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                request_params = {
                    'url': url,
                    'method': method,
                    'headers': headers,
                    'ssl': False  # 跳过SSL验证以兼容自签名证书
                }
                
                if json_data and method in ['POST', 'PUT', 'PATCH']:
                    request_params['json'] = json_data
                
                async with session.request(**request_params) as response:
                    response_time = asyncio.get_event_loop().time() - start_time
                    
                    # 读取响应内容
                    response_text = await response.text()
                    
                    # 检查状态码
                    status_ok = response.status == expected_status
                    
                    # 检查关键字
                    keyword_ok = True
                    if expected_keyword:
                        keyword_ok = expected_keyword in response_text
                    
                    # 检查响应时间
                    response_time_ok = response_time <= max_response_time
                    
                    # 综合判断
                    is_normal = status_ok and keyword_ok and response_time_ok
                    
                    # 构建消息
                    message_parts = []
                    if not status_ok:
                        message_parts.append(f"状态码: {response.status} (期望: {expected_status})")
                    if not keyword_ok:
                        message_parts.append(f"未找到关键字: {expected_keyword}")
                    if not response_time_ok:
                        message_parts.append(f"响应时间: {response_time:.2f}s (超时: {max_response_time}s)")
                    
                    message = "API检查正常" if is_normal else f"API异常: {'; '.join(message_parts)}"
                    
                    # 构建详细信息
                    details = {
                        'url': url,
                        'method': method,
                        'actual_status': response.status,
                        'expected_status': expected_status,
                        'response_time': round(response_time, 3),
                        'max_response_time': max_response_time,
                        'response_size': len(response_text),
                        'has_expected_keyword': keyword_ok if expected_keyword else None,
                        'headers': dict(response.headers)
                    }
                    
                    # 如果是错误响应，包含部分响应内容
                    if not is_normal and response_text:
                        # 只截取前200个字符避免数据过大
                        details['response_preview'] = response_text[:200] + ('...' if len(response_text) > 200 else '')
                    
                    return {
                        'is_normal': is_normal,
                        'value': response.status,
                        'response_time': response_time,
                        'message': message,
                        'details': details
                    }
                        
        except asyncio.TimeoutError:
            response_time = asyncio.get_event_loop().time() - start_time
            return {
                'is_normal': False,
                'response_time': response_time,
                'message': f"API请求超时: {timeout}秒"
            }
        except aiohttp.ClientError as e:
            response_time = asyncio.get_event_loop().time() - start_time
            return {
                'is_normal': False,
                'response_time': response_time,
                'message': f"API请求失败: {str(e)}"
            }
        except Exception as e:
            response_time = asyncio.get_event_loop().time() - start_time
            return {
                'is_normal': False,
                'response_time': response_time,
                'message': f"API请求异常: {str(e)}"
            }