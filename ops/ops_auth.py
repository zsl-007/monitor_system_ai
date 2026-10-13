"""
AI 运维 API 服务认证
"""

import os

from fastapi import Header, HTTPException


OPS_API_TOKEN = os.getenv(
    "OPS_API_TOKEN",
    ""
)


async def verify_ops_token(
    x_ops_token: str = Header(
        default=""
    )
):

    # 开发环境允许不设置
    if not OPS_API_TOKEN:
        return True

    if x_ops_token != OPS_API_TOKEN:

        raise HTTPException(
            status_code=401,
            detail="无效的运维API Token"
        )

    return True