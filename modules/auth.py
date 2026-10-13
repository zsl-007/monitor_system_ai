# auth.py
"""
身份认证模块
负责用户登录、JWT令牌管理和密码验证
"""

import hashlib
import jwt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Request,Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# 使用统一的日志配置
from modules.logger import logger

from modules.database import execute_single, execute_insert, execute_update

# JWT配置
SECRET_KEY = "your-secret-key-change-in-production"  # 生产环境请修改
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

"""
# 生产环境
import os
from dotenv import load_dotenv
# 加载环境变量
load_dotenv()
# JWT配置 - 从环境变量读取
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))

可以使用generate_secret.py来生成随机密钥

在部署的服务器上设置系统环境变量：
Linux/MacOS
export JWT_SECRET_KEY="your-very-secure-production-key"
Windows
set JWT_SECRET_KEY=your-production-key
"""

# 验证码配置
CAPTCHA_EXPIRE_MINUTES = 5

security = HTTPBearer()

class AuthManager:
    """认证管理器"""
    
    def __init__(self):
        self.captcha_cache = {}  # 存储验证码 {session_id: {"code": "1234", "expires": datetime}}
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password
    
    def get_password_hash(self, password: str) -> str:
        """生成密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """验证用户"""
        try:
            user = execute_single('SELECT * FROM users WHERE username = ? AND is_active = 1', (username,))
            if not user:
                return None
            
            if self.verify_password(password, user['password_hash']):
                return dict(user)
            return None
        except Exception as e:
            logger.error(f"认证用户失败: {e}")#print(f"认证用户失败: {e}")
            return None
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """创建JWT访问令牌"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证JWT令牌"""
        try:
            # 检查令牌是否在黑名单中
            blacklisted = execute_single(
                'SELECT id FROM token_blacklist WHERE token = ? AND expires_at > ?',
                (token, datetime.utcnow())
            )
            if blacklisted:
                return None
            
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.PyJWTError:
            return None
    
    def add_to_blacklist(self, token: str, expires_at: datetime):
        """将令牌加入黑名单"""
        try:
            execute_insert(
                'INSERT INTO token_blacklist (token, expires_at) VALUES (?, ?)',
                (token, expires_at)
            )
            return True
        except Exception as e:
            logger.error(f"添加令牌到黑名单失败: {e}")#print(f"添加令牌到黑名单失败: {e}")
            return False
    
    def generate_captcha(self, session_id: str) -> Dict[str, Any]:
        """生成验证码"""
        # 生成4位数字验证码
        code = ''.join([str(secrets.randbelow(10)) for _ in range(4)])
        expires = datetime.now() + timedelta(minutes=CAPTCHA_EXPIRE_MINUTES)
        
        self.captcha_cache[session_id] = {
            "code": code,
            "expires": expires
        }
        
        # 清理过期验证码
        self._clean_expired_captcha()
        
        return {
            "code": code,
            "image_data": self._generate_captcha_image(code)  # 简单实现，实际可以使用PIL生成图片
        }
    
    def verify_captcha(self, session_id: str, code: str) -> bool:
        """验证验证码"""
        captcha_data = self.captcha_cache.get(session_id)
        if not captcha_data:
            return False
        
        if datetime.now() > captcha_data["expires"]:
            del self.captcha_cache[session_id]
            return False
        
        is_valid = captcha_data["code"] == code
        if is_valid:
            del self.captcha_cache[session_id]
        
        return is_valid
    
    def _generate_captcha_image(self, code: str) -> str:
        """生成验证码图片（简单实现）"""
        # 这里可以集成PIL生成图片，为了简化，我们返回Base64编码的简单SVG
        import base64
        svg = f'''
        <svg width="120" height="40" xmlns="http://www.w3.org/2000/svg">
            <rect width="100%" height="100%" fill="#f8f9fa"/>
            <text x="60" y="25" font-family="Arial" font-size="20" text-anchor="middle" fill="#333">{code}</text>
        </svg>
        '''
        return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}"
    
    def _clean_expired_captcha(self):
        """清理过期验证码"""
        current_time = datetime.now()
        expired_keys = [
            key for key, data in self.captcha_cache.items() 
            if current_time > data["expires"]
        ]
        for key in expired_keys:
            del self.captcha_cache[key]

# 全局认证管理器实例
auth_manager = AuthManager()

async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = None):
    """获取当前用户 - 用于API调用"""
    if credentials is None:
        # 从cookie获取token
        token = request.cookies.get("access_token")
    else:
        token = credentials.credentials
    
    if not token:
        # 对于API调用，返回JSON错误
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = auth_manager.verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {"username": username}

async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """获取当前活跃用户 - 验证用户状态"""
    logger.debug('get_current_active_user')#print('get_current_active_user')
    if current_user is None:
        raise HTTPException(status_code=401, detail="用户未登录")
    
    # 从数据库查询用户状态
    try:
        user = execute_single(
            'SELECT * FROM users WHERE username = ?', 
            (current_user['username'],)
        )

        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        
        if not user['is_active']:
            raise HTTPException(status_code=401, detail="用户已被禁用")

        # 返回完整的用户信息
        return {
            "username": user['username'],
            "is_active": user['is_active'],
            "user_id": user['id']
        }
            
    except HTTPException:
        logger.error('HTTPException')#print('HTTPException')
        raise
    except Exception as e:
        logger.error(f"获取用户状态失败: {e}")#print(f"获取用户状态失败: {e}")
        raise HTTPException(status_code=500, detail="无法验证用户状态")
    
async def check_auth_for_page(request: Request) -> bool:
    """检查页面访问的认证状态"""
    #专门用于页面认证的函数
    token = request.cookies.get("access_token")
    if not token:
        return False
    
    try:
        payload = auth_manager.verify_token(token)
        return payload is not None and payload.get("sub") is not None
    except Exception:
        return False