# installdb.py
"""
初始化数据库脚本
创建数据库表结构和默认数据
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import initialize_database, check_database_health

def main():
    """主函数"""
    print("开始初始化数据库...")
    
    # 初始化数据库
    success = initialize_database()
    
    if success:
        # 检查数据库健康状态
        health_status = check_database_health()
        print(f"数据库初始化成功!")
        print(f"状态: {health_status['status']}")
        print(f"消息: {health_status['message']}")
        print(f"可用表: {', '.join(health_status['details']['available_tables'])}")
        
        print("\n默认用户信息:")
        print("用户名: jc_admin")
        print("密码: xhx_jc@2025!")
        
    else:
        print("数据库初始化失败!")
        sys.exit(1)

if __name__ == "__main__":
    main()