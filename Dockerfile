# 使用 Python 3.12 官方镜像（基于 Debian，内部 glibc 较新，与宿主机隔离）
# 考虑使用 Python 3.8 或 3.9，它们对 CentOS 7 兼容性更好
FROM python:3.9-slim

# 设置工作目录
WORKDIR /monitor_system

# 创建授权文件目录（文件将在运行时挂载）
RUN mkdir -p /monitor_system/license

# 设置环境变量，防止 Python 生成 .pyc 文件，并立即输出日志
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装系统级依赖（如果你的 python 包需要编译，比如 psutil 可能需要 gcc）
# slim 镜像通常没有 gcc，如果需要编译 C 扩展，建议先用 build 镜像编译好 wheel，或者安装 build-essential
# 这里假设 requirements 里的包都有预编译的 wheel，否则需要安装 gcc
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 复制项目代码
COPY monitor_system/ ./monitor_system/

# 暴露端口，默认为 3000，如果你的应用使用不同的端口，请相应更改
EXPOSE 18771

# 设置启动命令 (假设你的脚本是 main.py)
# 监控类程序通常是死循环，不需要 sleep
CMD ["python", "monitor_system/run.py"]