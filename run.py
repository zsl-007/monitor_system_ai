# run.py
"""
启动脚本
"""

import uvicorn
import sys
from modules.license import license_auth

if __name__ == "__main__":
    result_auth = license_auth()
    if result_auth['code'] != 1:
        print(f"auth error:{result_auth['result']['message']}")
        sys.exit()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=18770,
        reload=False,  # 开发时启用热重载
        log_level="info"
    )