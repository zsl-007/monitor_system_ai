
"""
恢复初始化密码
"""
from modules.auth import auth_manager
from modules.database import execute_update
from datetime import datetime

def main():
    default_password = "xhx_jc@2025!"
    password_hash = auth_manager.get_password_hash(default_password)
    success = execute_update(
        'UPDATE users SET password_hash = ?, updated_time = ? WHERE username = ?',
        (password_hash, datetime.now().isoformat(), 'jc_admin')
    )
    
    if success:
        print('密码初始化成功：用户名（jc_admin），密码（xhx_jc@2025!）')
        return
    else:
        print('恢复初始化密码失败！')
        return

if __name__ == "__main__":
    main()    