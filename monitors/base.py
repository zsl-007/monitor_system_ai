# monitors/base.py
"""
监控器基类
"""

from typing import Dict, Any
from abc import ABC, abstractmethod
import time

class BaseMonitor(ABC):
    """监控器基类 - 优化版本"""
    
    async def check(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行监控检查 - 带性能监控
        
        Args:
            config: 监控配置
            
        Returns:
            监控结果
        """
        start_time = time.time()
        
        try:
            result = await self._check_impl(config)
            execution_time = time.time() - start_time
            
            # 记录执行时间
            if 'details' not in result:
                result['details'] = {}
            result['details']['execution_time'] = round(execution_time, 3)
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                'is_normal': False,
                'message': f"监控检查异常: {str(e)}",
                'details': {
                    'execution_time': round(execution_time, 3),
                    'error': str(e)
                }
            }
    
    @abstractmethod
    async def _check_impl(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        具体的监控检查实现
        
        Args:
            config: 监控配置
            
        Returns:
            监控结果
        """
        pass