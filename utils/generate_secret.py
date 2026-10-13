# generate_secret.py

import secrets
import base64

# 为生产环境提供安全密钥 auth.py 中使用
def generate_secure_key():
    """生成安全的随机密钥"""
    # 方法1: 使用 secrets 模块
    key = secrets.token_urlsafe(32)
    print(f"JWT_SECRET_KEY={key}")
    
    # 方法2: 使用 base64 编码的随机字节
    key_bytes = secrets.token_bytes(32)
    key_base64 = base64.urlsafe_b64encode(key_bytes).decode()
    print(f"JWT_SECRET_KEY={key_base64}")

if __name__ == "__main__":
    generate_secure_key()