# main.py
"""
监控系统Web界面主应用
提供配置页面、实时状态、报警数据、历史数据等功能
"""
import json
import os
import ast

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException,Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from fastapi import Depends, Response
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


# 使用统一的日志配置
from modules.logger import logger
from modules.config import ConfigManager
from modules.scheduler import TaskScheduler
from modules.alert import AlertManager
from modules.alert import AlertRecord
from modules.database import get_db_connection, execute_query, execute_single, execute_update, execute_insert, initialize_database, check_database_health  # 新增导入
from modules.auth import auth_manager, get_current_user, get_current_active_user,check_auth_for_page

from routers.ops import router as ops_router    #2026-8-31，适配AI新增代码
from routers.ops import set_task_scheduler  #2026-8-31，适配AI新增代码

# 创建应用实例
app = FastAPI(title="系统监测平台", version="1.0.0")

app.include_router(ops_router)  #2026-8-31，适配AI新增代码

# 添加时间格式化过滤器函数
def format_timestamp_filter(timestamp):
    """格式化时间戳为可读字符串"""
    if timestamp is None:
        return "从未执行"
    
    try:
        # 如果timestamp是浮点数（Unix时间戳）
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        # 如果已经是字符串，直接返回
        elif isinstance(timestamp, str):
            return timestamp
        else:
            return str(timestamp)
    except Exception:
        return str(timestamp)

import sys

# 路径处理函数
def get_base_path():
    """获取基础路径"""
    if getattr(sys, 'frozen', False):
        # 打包环境
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        else:
            return os.path.dirname(sys.executable)
    else:
        # 开发环境
        return os.path.dirname(__file__)

# 设置模板和静态文件路径
BASE_PATH = get_base_path()

def setup_directories():
    """设置目录路径"""
    # 模板目录
    template_dirs = [
        os.path.join(BASE_PATH, 'templates'),
        'templates',  # 开发环境
        os.path.join(os.path.dirname(__file__), 'templates')  # 备用
    ]
    
    static_dirs = [
        os.path.join(BASE_PATH, 'static'),
        'static',  # 开发环境
        os.path.join(os.path.dirname(__file__), 'static')  # 备用
    ]
    
    # 找到存在的模板目录
    template_dir = None
    for dir_path in template_dirs:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            template_dir = dir_path
            break
    
    # 找到存在的静态目录
    static_dir = None
    for dir_path in static_dirs:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            static_dir = dir_path
            break
    
    return template_dir, static_dir

# 在应用初始化之前调用
template_dir, static_dir = setup_directories()

if template_dir is None:
    raise Exception("未找到模板目录")
if static_dir is None:
    raise Exception("未找到静态文件目录")

#print(f"模板目录: {template_dir}")
#print(f"静态文件目录: {static_dir}")
logger.debug(f"模板目录: {template_dir}")
logger.debug(f"静态文件目录: {static_dir}")

# 修改模板配置
templates = Jinja2Templates(directory=template_dir)
templates.env.filters["format_timestamp"] = format_timestamp_filter
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 配置模板和静态文件
"""
templates = Jinja2Templates(directory="templates")
templates.env.filters["format_timestamp"] = format_timestamp_filter
app.mount("/static", StaticFiles(directory="static"), name="static")
"""

m_Version = "1.1.1" # 系统版本号

# 全局实例
config_manager = ConfigManager()
task_scheduler: Optional[TaskScheduler] = None

# 增加webhook推送
from modules.webhook import WebhookManager
webhook_manager = WebhookManager()

# 数据模型
class MonitorConfigCreate(BaseModel):
    name: str
    type: str
    target: str
    enabled: bool = True
    interval_seconds: int = 60
    threshold: Dict[str, Any] = {}
    extra_config: Dict[str, Any] = {}

class MonitorConfigUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    target: Optional[str] = None
    enabled: Optional[bool] = None
    interval_seconds: Optional[int] = None
    threshold: Optional[Dict[str, Any]] = None
    extra_config: Optional[Dict[str, Any]] = None

class EmailConfigUpdate(BaseModel):
    smtp_server: str
    smtp_port: int
    username: str
    password: str
    sender: str
    receivers: List[str]
    ssl_enabled: bool = False

# 在 main.py 的模型定义部分添加认证相关模型
class LoginRequest(BaseModel):
    username: str
    password: str
    captcha: str
    session_id: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库和调度器"""
    # 初始化数据库
    logger.info("开始启动系统监测平台...")
    if not initialize_database():
        logger.info("数据库初始化失败！")
        return
    
    # ===== 新增：数据库已就绪，重新加载 Webhook 配置 =====
    # 顶层创建 WebhookManager 时表还不存在，这里补一次加载
    webhook_manager._load_webhooks()
    # ====================================================    

    # 检查数据库健康状态
    #health_status = check_database_health()
    #logger.info(f"数据库健康状态: {health_status['status']} - {health_status['message']}")
    
    # 初始化调度器
    global task_scheduler
    try:
        task_scheduler = TaskScheduler(config_manager)
        await task_scheduler.start()

        set_task_scheduler(task_scheduler)  # 将 TaskScheduler 注入 AI 运维 API #2026-8-31，适配AI新增代码

        logger.info("任务调度器启动成功")
    except Exception as e:
        logger.error(f"启动调度器失败: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时停止调度器"""
    global task_scheduler
    if task_scheduler:
        await task_scheduler.stop()

# 添加数据库健康检查API
@app.get("/api/database-health")
async def get_database_health():
    """获取数据库健康状态"""
    return check_database_health()

# 在应用实例创建后添加中间件
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """认证中间件，处理未认证用户的自动重定向"""
    # 检查是否需要认证的路径
    protected_paths = ["/", "/config", "/status", "/alerts", "/history"]
    current_path = request.url.path
    
    # API路径不需要重定向（它们应该返回JSON错误）
    is_api_path = current_path.startswith("/api/")
    is_protected_path = current_path in protected_paths
    
    if is_protected_path and not is_api_path:
        # 检查认证令牌
        token = request.cookies.get("access_token")
        if not token:
            # 未认证，重定向到登录页面
            return RedirectResponse(url="/login")
        
        # 验证令牌
        try:
            payload = auth_manager.verify_token(token)
            if not payload:
                # 令牌无效，重定向到登录页面
                return RedirectResponse(url="/login")
        except Exception:
            # 令牌验证出错，重定向到登录页面
            return RedirectResponse(url="/login")
    
    # 继续处理请求
    response = await call_next(request)
    return response

# 添加数据库初始化API（用于手动重新初始化）
# 如果需要在已存在的数据库上重新初始化，可以调用：
# curl -X POST http://localhost:8000/api/initialize-database
@app.post("/api/initialize-database")
async def initialize_database_api():
    """手动初始化数据库"""
    success = initialize_database()
    if success:
        return {"success": True, "message": "数据库初始化成功"}
    else:
        raise HTTPException(status_code=500, detail="数据库初始化失败")

# 在 main.py 的路由部分添加认证路由
security = HTTPBearer()

# 认证相关的API路由
@app.post("/api/login")
async def login(login_data: LoginRequest, response: Response):
    """用户登录"""
    try:
        # 验证验证码
        if not auth_manager.verify_captcha(login_data.session_id, login_data.captcha):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "验证码错误"}
            )
        
        # 验证用户
        user = auth_manager.authenticate_user(login_data.username, login_data.password)
        if not user:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "用户名或密码错误"}
            )
        
        # 创建访问令牌
        access_token = auth_manager.create_access_token(
            data={"sub": user['username']}
        )
        
        # 设置HTTP-only cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=30 * 60,  # 30分钟
            secure=False,  # 生产环境应该设置为True
            samesite="lax"
        )
        
        # 返回与前端期望格式一致的数据
        return {
            "success": True,
            "message": "登录成功",
            "access_token": access_token,
            "token_type": "bearer"
        }
        
    except Exception as e:
        logger.error(f"登录过程出错: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "登录过程出现错误"}
        )
    
@app.post("/api/logout")
async def logout(response: Response, current_user: dict = Depends(get_current_user)):
    """用户登出"""
    try:
        # 这里可以添加令牌黑名单逻辑
        # token = None
        # 这里需要从请求中获取token，简化处理        
        response.delete_cookie("access_token")
        return {"success": True, "message": "登出成功"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "登出失败"}
        )

@app.post("/api/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    confirm_password: str,
    current_user: dict = Depends(get_current_active_user) # 修改密码需要活跃状态
):
    """修改当前用户密码"""
    try:
        logger.debug(f"收到修改密码请求，用户: {current_user['username']}")
        logger.debug(f"当前密码长度: {len(current_password)}")
        logger.debug(f"新密码长度: {len(new_password)}")
        logger.debug(f"确认密码长度: {len(confirm_password)}")

        if new_password != confirm_password:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "新密码和确认密码不一致"}
            )
        
        if len(new_password) < 6:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "密码长度至少6位"}
            )
        
        # 验证当前密码
        user = auth_manager.authenticate_user(current_user['username'], current_password)
        if not user:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "当前密码错误"}
            )
        
        # 更新密码
        new_password_hash = auth_manager.get_password_hash(new_password)
        success = execute_update(
            'UPDATE users SET password_hash = ?, updated_time = ? WHERE username = ?',
            (new_password_hash, datetime.now().isoformat(), current_user['username'])
        )
        
        if success:
            return {"success": True, "message": "密码修改成功"}
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "密码修改失败"}
            )
            
    except Exception as e:
        logger.error(f"修改密码出错: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "修改密码过程出现错误"}
        )    

@app.post("/api/captcha")
async def get_captcha(request: dict):
    """获取验证码"""
    try:
        session_id = request.get('session_id')
        if not session_id:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "缺少session_id"}
            )
        
        captcha_data = auth_manager.generate_captcha(session_id)
        return {
            "success": True, 
            "image_data": captcha_data['image_data']
        }
    except Exception as e:
        logger.error(f"生成验证码出错: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "生成验证码失败"}
        )
            
# 添加登录页面路由（不需要认证）
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面 - 不需要认证"""
    # 如果已经登录，重定向到首页
    is_authenticated = await check_auth_for_page(request)
    if is_authenticated:
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse("login.html", {"request": request})

# 页面路由
@app.get("/", response_class=HTMLResponse)
async def root_page(request: Request):
    """根页面 - 自动重定向"""
    # 使用中间件处理重定向，这里只需要返回状态页面
    return RedirectResponse(url="/status")

# 修改所有页面路由，使用通用上下文
@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request, current_user: dict = Depends(get_current_user)):
    # 检查认证
    is_authenticated = await check_auth_for_page(request)
    if not is_authenticated:
        return RedirectResponse(url="/login")

    """配置页面"""
    monitor_configs = config_manager.get_all_monitor_configs()
    email_config = config_manager.get_email_config()
    monitor_types = config_manager.get_monitor_types()
    #project_name = config_manager.get_project_name()
    webhooks = webhook_manager.get_all_webhooks()   # 增加webhook推送

    # 获取磁盘分区信息
    from monitors.system import SystemMonitor
    disk_monitor = SystemMonitor()
    disk_partitions = disk_monitor.get_disk_partitions()

    # 获取网络接口信息
    network_interfaces = disk_monitor.get_network_interfaces()

    context = await get_common_context(request, current_user) # 传递current_user
    context.update({
        "monitor_configs": monitor_configs,
        "email_config": email_config,
        "monitor_types": monitor_types,
        "webhooks": webhooks,                     # ← 新增 webhook推送
        "default_thresholds": {
            monitor_type: config_manager.get_default_thresholds(monitor_type)
            for monitor_type in monitor_types
        },
        "disk_partitions": disk_partitions,  # 添加磁盘分区信息
        "network_interfaces": network_interfaces  # 添加网络接口信息
    })
    
    return templates.TemplateResponse("config.html", context)

@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request, current_user: dict = Depends(get_current_user)):
    """实时状态页面"""
    # 检查认证
    is_authenticated = await check_auth_for_page(request)
    if not is_authenticated:
        return RedirectResponse(url="/login")
        
    # 获取最新的监控数据（每个监控项的最新一条）
    query = '''
        SELECT md.*, mc.name as config_name, mc.type as monitor_type, mc.threshold as threshold_config
        FROM monitor_data md
        INNER JOIN (
            SELECT config_id, MAX(created_time) as max_time
            FROM monitor_data
            GROUP BY config_id
        ) latest ON md.config_id = latest.config_id AND md.created_time = latest.max_time
        INNER JOIN monitor_configs mc ON md.config_id = mc.id
        WHERE mc.enabled = 1
        ORDER BY mc.type, mc.name
    '''
    
    status_data = []
    rows = execute_query(query)
    
    for row in rows:
        # 健壮的阈值配置解析
        threshold_config = {}
        if row['threshold_config']:
            threshold_str = row['threshold_config'].strip()
            
            # 方法1: 直接JSON解析
            try:
                threshold_config = json.loads(threshold_str)
            except json.JSONDecodeError:
                # 方法2: 尝试修复常见的JSON格式问题
                try:
                    # 替换单引号为双引号
                    fixed_str = threshold_str.replace("'", '"')
                    threshold_config = json.loads(fixed_str)
                except json.JSONDecodeError:
                    # 方法3: 使用ast.literal_eval解析Python字面量
                    try:
                        threshold_config = ast.literal_eval(threshold_str)
                    except (ValueError, SyntaxError):
                        # 方法4: 如果是简单的键值对格式
                        try:
                            threshold_config = {}
                            # 移除花括号
                            clean_str = threshold_str.strip('{}')
                            pairs = clean_str.split(',')
                            for pair in pairs:
                                if ':' in pair:
                                    key, value = pair.split(':', 1)
                                    key = key.strip().strip('"\'')
                                    value = value.strip()
                                    # 尝试转换数值
                                    try:
                                        if value.isdigit() or (value.replace('.', '').isdigit() and value.count('.') == 1):
                                            value = float(value) if '.' in value else int(value)
                                        elif value.lower() in ['true', 'false']:
                                            value = value.lower() == 'true'
                                    except:
                                        pass
                                    threshold_config[key] = value
                        except:
                            # 所有方法都失败，使用空字典
                            threshold_config = {}
        
        row['threshold_config'] = threshold_config
        
        # 处理时间显示，移除时区信息
        if row['created_time']:
            if isinstance(row['created_time'], str):
                try:
                    dt = datetime.fromisoformat(row['created_time'].replace('Z', '+00:00'))
                    row['created_time'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    # 如果解析失败，保持原样
                    pass
        status_data.append(row)
    
    # 获取运行中的任务信息
    running_tasks = []
    if task_scheduler:
        running_tasks = task_scheduler.get_running_tasks()
        # 处理任务时间显示
        for task in running_tasks:
            if task.get('next_run_time'):
                if hasattr(task['next_run_time'], 'strftime'):
                    # 如果是datetime对象，格式化显示
                    task['next_run_time'] = task['next_run_time'].strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(task['next_run_time'], str):
                    # 如果是字符串，移除时区信息
                    task['next_run_time'] = task['next_run_time'].split('+')[0]
    
    # 获取调度器执行统计
    execution_stats = {}
    if task_scheduler:
        execution_stats = task_scheduler.get_execution_stats()

    # 新增：获取当日报警统计数据
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.now()
    
    alert_stats_query = '''
        SELECT 
            mc.id as config_id,
            mc.name as config_name,
            mc.type as monitor_type,
            mc.enabled as is_enabled,
            COUNT(ad.id) as alert_count
        FROM monitor_configs mc
        LEFT JOIN alert_data ad ON mc.id = ad.config_id 
            AND ad.alert_time >= ? AND ad.alert_time <= ?
        GROUP BY mc.id, mc.name, mc.type, mc.enabled
        ORDER BY mc.type, mc.name
    '''
    
    alert_stats = execute_query(alert_stats_query, (today_start, today_end))
    
    # 处理统计数据
    health_stats = []
    for stat in alert_stats:
        health_stats.append({
            'config_id': stat['config_id'],
            'config_name': stat['config_name'],
            'monitor_type': stat['monitor_type'],
            'is_enabled': stat['is_enabled'],
            'alert_count': stat['alert_count'] or 0
        })

    context = await get_common_context(request, current_user) # 传递current_user
    context.update({
        "request": request,
        "status_data": status_data,
        "running_tasks": running_tasks,
        "scheduler_status": task_scheduler.get_scheduler_status() if task_scheduler else {},
        "execution_stats": execution_stats,
        "health_stats": health_stats,  # 新增健康统计数据
        "today_date": datetime.now().strftime('%Y-%m-%d')  # 当前日期        
    })
    
    return templates.TemplateResponse("status.html", context)    

@app.get("/alerts", response_class=HTMLResponse)
async def alerts_page(
    request: Request,
    current_user: dict = Depends(get_current_user),
    start_date: str = None, 
    end_date: str = None,
    config_id: str = None,  # 新增：监控项目筛选
    page: int = 1,
    per_page: int = 20  # 确保这个参数被正确接收
):
    # 检查认证
    is_authenticated = await check_auth_for_page(request)
    if not is_authenticated:
        return RedirectResponse(url="/login")
        
    """报警数据页面 - 支持分页"""
    # 处理 config_id 参数 - 将空字符串转换为 None
    if config_id == "":
        config_id = None
    else:
        # 如果 config_id 不是空字符串，尝试转换为整数
        try:
            config_id = int(config_id) if config_id else None
        except (ValueError, TypeError):
            config_id = None
    
    # 处理日期参数
    if not start_date or not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        start_dt = datetime.now() - timedelta(days=7)
        end_dt = datetime.now() + timedelta(days=1)
        start_date = start_dt.strftime('%Y-%m-%d')
        end_date = end_dt.strftime('%Y-%m-%d')

    # 获取监控配置列表（用于下拉框）
    monitor_configs = config_manager.get_all_monitor_configs()

    # 获取报警数据 - 使用分页
    # 计算总数
    count_query = '''
        SELECT COUNT(*) as total 
        FROM alert_data ad
        LEFT JOIN monitor_configs mc ON ad.config_id = mc.id
        WHERE ad.alert_time >= ? AND ad.alert_time <= ?
    '''
    count_params = [start_dt, end_dt]

    # 添加监控项目筛选条件
    if config_id:
        count_query += ' AND ad.config_id = ?'
        count_params.append(config_id)
    
    total_count = execute_single(count_query, tuple(count_params))['total']
    total_pages = (total_count + per_page - 1) // per_page
    
    # 确保页码在有效范围内
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages
    
    # 计算分页偏移
    offset = (page - 1) * per_page
    
    # 获取分页数据
    query = '''
        SELECT ad.*, mc.name as config_name 
        FROM alert_data ad
        LEFT JOIN monitor_configs mc ON ad.config_id = mc.id
        WHERE ad.alert_time >= ? AND ad.alert_time <= ?
    '''
    query_params = [start_dt, end_dt]    

    # 添加监控项目筛选条件
    if config_id:
        query += ' AND ad.config_id = ?'
        query_params.append(config_id)
    
    query += ' ORDER BY ad.alert_time DESC LIMIT ? OFFSET ?'
    query_params.extend([per_page, offset])

    alerts_data = execute_query(query, tuple(query_params))
    
    # ===== 新增：为每条报警附加 Webhook 推送记录 =====
    alert_ids = [row['id'] for row in alerts_data]
    records_map = webhook_manager.get_push_records_for_alerts(alert_ids)
    alerts_data = [
        {**dict(row), 'webhook_records': records_map.get(row['id'], [])}
        for row in alerts_data
    ]
    # ==================================================
        
    # 分页信息
    pagination = {
        "page": page,
        "per_page": per_page,
        "total": total_count,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else 1,
        "next_page": page + 1 if page < total_pages else total_pages
    }
    
    context = await get_common_context(request, current_user) # 传递current_user
    context.update({
        "request": request,
        "alerts_data": alerts_data,
        "monitor_configs": monitor_configs,  # 新增：监控配置列表
        "selected_config_id": config_id,     # 新增：选中的监控项目ID        
        "start_date": start_date,
        "end_date": end_date,
        "pagination": pagination,
        "current_page": page,
        "per_page": per_page
    })
    
    return templates.TemplateResponse("alerts.html", context)    

@app.get("/api/export-alerts")
async def export_alerts(start_date: str, end_date: str, config_id: int = None):
    """导出报警数据为CSV"""
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误")
    
    query = '''
        SELECT ad.*, mc.name as config_name 
        FROM alert_data ad
        LEFT JOIN monitor_configs mc ON ad.config_id = mc.id
        WHERE ad.alert_time >= ? AND ad.alert_time <= ?
    '''
    params = [start_dt, end_dt]

    # 添加监控项目筛选条件
    if config_id:
        query += ' AND ad.config_id = ?'
        params.append(config_id)
    
    query += ' ORDER BY ad.alert_time DESC'

    rows = execute_query(query, tuple(params))
    
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(['时间', '监控项目', '监控类型', '报警信息', '是否发送','接收人', 'Webhook推送'])

    # 写入数据
    alert_ids = [row['id'] for row in rows]
    records_map = webhook_manager.get_push_records_for_alerts(alert_ids)

    for row in rows:
        wh_records = records_map.get(row['id'], [])
        if wh_records:
            wh_summary = "; ".join(
                f"{r['webhook_name']}:{'OK' if r['success'] else 'FAIL'}"
                for r in wh_records
            )
        else:
            wh_summary = ''
        writer.writerow([
            row['alert_time'],
            row['config_name'] or 'N/A',
            row['monitor_type'],
            row['alert_message'],
            '是' if row['sent'] else '否',
            row['receiver'] or 'N/A',
            wh_summary
        ])    

    from fastapi.responses import StreamingResponse
    
    output.seek(0)

    # 根据筛选条件生成文件名
    filename = f"alerts_{start_date}_to_{end_date}"
    if config_id:
        # 获取监控项目名称
        config = execute_single('SELECT name FROM monitor_configs WHERE id = ?', (config_id,))
        if config:
            config_name = config['name'].replace(' ', '_')
            filename += f"_{config_name}"
    filename += ".csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )    

# 在 main.py 的 API 路由部分修改历史数据API

@app.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    current_user: dict = Depends(get_current_user),
    start_date: str = None,
    end_date: str = None,
    config_id: str = None,
    status_filter: str = None,
    page: int = 1,
    per_page: int = 20
):
    # 检查认证
    is_authenticated = await check_auth_for_page(request)
    if not is_authenticated:
        return RedirectResponse(url="/login")
        
    """历史数据页面 - 支持分页和状态筛选"""
    
    # 处理 config_id 参数 - 将空字符串转换为 None
    if config_id == "":
        config_id = None
    else:
        # 如果 config_id 不是空字符串，尝试转换为整数
        try:
            config_id = int(config_id) if config_id else None
        except (ValueError, TypeError):
            config_id = None
    
    # 处理状态筛选参数
    if status_filter == "":
        status_filter = None
    
    # 处理日期参数
    if start_date is None or end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    try:
        # 修正时间范围计算 - 确保包含完整的开始和结束日期
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    except ValueError as e:
        start_dt = datetime.now() - timedelta(days=1)
        end_dt = datetime.now() + timedelta(days=1)
        start_date = start_dt.strftime('%Y-%m-%d')
        end_date = end_dt.strftime('%Y-%m-%d')
    
    # 获取监控配置列表
    monitor_configs = config_manager.get_all_monitor_configs()
    
    # 计算总数 - 用于分页
    count_query = '''
        SELECT COUNT(*) as total
        FROM monitor_data md
        INNER JOIN monitor_configs mc ON md.config_id = mc.id
        WHERE md.created_time >= ? AND md.created_time < ?
    '''
    count_params = [start_dt, end_dt]
    
    if config_id:
        count_query += ' AND md.config_id = ?'
        count_params.append(config_id)
    
    # 添加状态筛选条件
    if status_filter == 'normal':
        count_query += ' AND md.is_normal = 1'
    elif status_filter == 'abnormal':
        count_query += ' AND md.is_normal = 0'
    
    total_count = execute_single(count_query, tuple(count_params))['total']
    
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
    
    # 计算全部筛选条件下的正常和异常记录数（不受分页影响）
    stats_query = '''
        SELECT 
            SUM(CASE WHEN md.is_normal = 1 THEN 1 ELSE 0 END) as normal_count,
            SUM(CASE WHEN md.is_normal = 0 THEN 1 ELSE 0 END) as abnormal_count
        FROM monitor_data md
        INNER JOIN monitor_configs mc ON md.config_id = mc.id
        WHERE md.created_time >= ? AND md.created_time < ?
    '''
    stats_params = [start_dt, end_dt]
    
    if config_id:
        stats_query += ' AND md.config_id = ?'
        stats_params.append(config_id)
    
    # 注意：状态统计查询不考虑状态筛选条件，显示全部数据的状态分布
    stats_result = execute_single(stats_query, tuple(stats_params))
    normal_count = stats_result['normal_count'] or 0
    abnormal_count = stats_result['abnormal_count'] or 0
    
    # 确保页码在有效范围内
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages
    
    # 计算分页偏移
    offset = (page - 1) * per_page
    
    # 获取分页数据
    query = '''
        SELECT md.*, mc.name as config_name, mc.type as monitor_type
        FROM monitor_data md
        INNER JOIN monitor_configs mc ON md.config_id = mc.id
        WHERE md.created_time >= ? AND md.created_time < ?
    '''
    params = [start_dt, end_dt]
    
    if config_id:
        query += ' AND md.config_id = ?'
        params.append(config_id)
    
    # 添加状态筛选条件
    if status_filter == 'normal':
        query += ' AND md.is_normal = 1'
    elif status_filter == 'abnormal':
        query += ' AND md.is_normal = 0'
    
    query += ' ORDER BY md.created_time DESC LIMIT ? OFFSET ?'
    params.extend([per_page, offset])
    
    history_data = execute_query(query, tuple(params))
    
    # 获取图表数据（按时间聚合）- 这部分不受分页和状态筛选影响
    chart_query = '''
        SELECT 
            md.config_id,
            mc.name as config_name,
            mc.type as monitor_type,
            datetime(md.created_time) as hour_time,
            AVG(md.value) as avg_value,
            COUNT(*) as data_count
        FROM monitor_data md
        INNER JOIN monitor_configs mc ON md.config_id = mc.id
        WHERE md.created_time >= ? AND md.created_time < ? AND md.value IS NOT NULL
    '''
    chart_params = [start_dt, end_dt]
    
    if config_id:
        chart_query += ' AND md.config_id = ?'
        chart_params.append(config_id)
    
    chart_query += '''
        GROUP BY md.config_id, hour_time
        ORDER BY hour_time
    '''
    
    chart_rows = execute_query(chart_query, tuple(chart_params))
    chart_data = {}
    for row in chart_rows:
        config_id_val = row['config_id']
        if config_id_val not in chart_data:
            chart_data[config_id_val] = {
                'config_name': row['config_name'],
                'monitor_type': row['monitor_type'],
                'data': []
            }
        
        # 确保时间字段不为None
        time_value = row['hour_time']
        if time_value is None:
            time_value = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        chart_data[config_id_val]['data'].append({
            'time': time_value,
            'value': round(row['avg_value'], 2) if row['avg_value'] is not None else 0
        })
    
    # 对图表数据进行采样，避免数据量过大
    for config_id_val, chart_info in chart_data.items():
        data_points = chart_info['data']
        if len(data_points) > 200:
            # 使用简单的等间隔采样
            step = max(1, len(data_points) // 200)
            chart_info['data'] = data_points[::step]
            # 确保最后一个点被包含
            if chart_info['data'][-1] != data_points[-1]:
                chart_info['data'].append(data_points[-1])
    
    # 分页信息
    pagination = {
        "page": page,
        "per_page": per_page,
        "total": total_count,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else 1,
        "next_page": page + 1 if page < total_pages else total_pages
    }
    
    context = await get_common_context(request, current_user) # 传递current_user
    context.update({
        "request": request,
        "history_data": history_data,
        "chart_data": chart_data,
        "monitor_configs": monitor_configs,
        "selected_config_id": config_id,
        "selected_status_filter": status_filter,
        "start_date": start_date,
        "end_date": end_date,
        "pagination": pagination,
        "current_page": page,
        "per_page": per_page,
        "normal_count": normal_count,
        "abnormal_count": abnormal_count
    })
    
    return templates.TemplateResponse("history.html", context)    

@app.get("/api/export-history")
async def export_history(start_date: str, end_date: str, config_id: int = None, status_filter: str = None):
    """导出历史数据为CSV - 支持状态筛选"""
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误")
    
    query = '''
        SELECT md.*, mc.name as config_name, mc.type as monitor_type
        FROM monitor_data md
        INNER JOIN monitor_configs mc ON md.config_id = mc.id
        WHERE md.created_time >= ? AND md.created_time <= ?
    '''
    params = [start_dt, end_dt]
    
    if config_id:
        query += ' AND md.config_id = ?'
        params.append(config_id)
    
    # 添加状态筛选条件
    if status_filter == 'normal':
        query += ' AND md.is_normal = 1'
    elif status_filter == 'abnormal':
        query += ' AND md.is_normal = 0'
    
    query += ' ORDER BY md.created_time DESC'
    
    rows = execute_query(query, tuple(params))
    
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(['时间', '监控项目', '监控类型', '监测值', '状态', '是否正常'])
    
    # 写入数据
    for row in rows:
        writer.writerow([
            row['created_time'],
            row['config_name'],
            row['monitor_type'],
            row['value'] if row['value'] is not None else '',
            row['status'] or '',
            '是' if row['is_normal'] else '否'
        ])
    
    from fastapi.responses import StreamingResponse
    
    output.seek(0)
    
    # 根据筛选条件生成文件名
    if status_filter:
        filename = f"history_{start_date}_to_{end_date}_{status_filter}.csv"
    else:
        filename = f"history_{start_date}_to_{end_date}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )    

# API路由 - 监控配置

@app.get("/api/monitor-configs/{config_id}")
async def get_monitor_config_api(config_id: int):
    """获取单个监控配置 API"""
    try:
        config = config_manager.get_monitor_config(config_id)
        if config:
            return {"success": True, "data": config}
        else:
            raise HTTPException(status_code=404, detail="监控配置不存在")
    except Exception as e:
        #logger.error(f"获取监控配置失败: {e}")
        raise HTTPException(status_code=500, detail="获取监控配置失败")

@app.post("/api/monitor-configs")
async def create_monitor_config(config: MonitorConfigCreate):
    """创建监控配置"""
    config_id = config_manager.create_monitor_config(config.dict())
    if config_id:
        # 重新加载调度器任务
        if task_scheduler:
            await task_scheduler.load_and_schedule_tasks()
        return {"success": True, "config_id": config_id}
    else:
        raise HTTPException(status_code=500, detail="创建监控配置失败")

@app.put("/api/monitor-configs/{config_id}")
async def update_monitor_config(config_id: int, config: MonitorConfigUpdate):
    """更新监控配置"""
    success = config_manager.update_monitor_config(config_id, config.dict(exclude_unset=True))
    if success:
        # 重新加载调度器任务
        if task_scheduler:
            await task_scheduler.load_and_schedule_tasks()
        return {"success": True}
    else:
        raise HTTPException(status_code=500, detail="更新监控配置失败")

@app.delete("/api/monitor-configs/{config_id}")
async def delete_monitor_config(config_id: int):
    """删除监控配置"""
    success = config_manager.delete_monitor_config(config_id)
    if success:
        # 重新加载调度器任务
        if task_scheduler:
            await task_scheduler.load_and_schedule_tasks()
        return {"success": True}
    else:
        raise HTTPException(status_code=500, detail="删除监控配置失败")

@app.post("/api/monitor-configs/{config_id}/toggle")
async def toggle_monitor_config(config_id: int, enabled: bool = Form(...)):
    """启用/禁用监控配置"""
    success = config_manager.toggle_monitor_config(config_id, enabled)
    if success:
        # 重新加载调度器任务
        if task_scheduler:
            await task_scheduler.load_and_schedule_tasks()
        return {"success": True}
    else:
        raise HTTPException(status_code=500, detail="切换监控配置状态失败")

# API路由 - 邮箱配置
@app.put("/api/email-config")
async def update_email_config(config: EmailConfigUpdate):
    """更新邮箱配置"""
    # 在初始化之后启动，以免如果没有数据库报错
    alert_manager = AlertManager()    

    config_dict = config.dict()
    config_dict['receivers'] = ';'.join(config.receivers)
    success = config_manager.update_email_config(config_dict)
    if success:
        # 重新加载报警管理器的邮箱配置
        alert_manager._load_email_config()
        return {"success": True}
    else:
        raise HTTPException(status_code=500, detail="更新邮箱配置失败")

@app.get("/api/disk-partitions")
async def get_disk_partitions():
    """获取磁盘分区列表"""
    try:
        from monitors.system import SystemMonitor
        monitor = SystemMonitor()
        partitions = monitor.get_disk_partitions()
        return {"success": True, "data": partitions}
    except Exception as e:
        return {"success": False, "error": f"获取磁盘分区失败: {str(e)}"}

# 在 main.py 的 API 路由部分添加

@app.get("/api/network-interfaces")
async def get_network_interfaces():
    """获取网络接口列表"""
    try:
        from monitors.system import SystemMonitor
        monitor = SystemMonitor()
        interfaces = monitor.get_network_interfaces()
        return {"success": True, "data": interfaces}
    except Exception as e:
        return {"success": False, "error": f"获取网络接口失败: {str(e)}"}
    
# API路由 - 实时数据
@app.get("/api/real-time-status")
async def get_real_time_status():
    """获取实时状态数据（用于AJAX更新）"""
    query = '''
        SELECT md.*, mc.name as config_name, mc.type as monitor_type
        FROM monitor_data md
        INNER JOIN (
            SELECT config_id, MAX(created_time) as max_time
            FROM monitor_data
            GROUP BY config_id
        ) latest ON md.config_id = latest.config_id AND md.created_time = latest.max_time
        INNER JOIN monitor_configs mc ON md.config_id = mc.id
        WHERE mc.enabled = 1
    '''
    
    status_data = execute_query(query)
    
    return {"success": True, "data": status_data}    

@app.post("/api/trigger-check/{config_id}")
async def trigger_immediate_check(config_id: int):
    """立即触发指定配置的检查"""
    if task_scheduler:
        success = await task_scheduler.trigger_immediate_check(config_id)
        return {"success": success}
    else:
        return {"success": False, "error": "调度器未运行"}

# API路由 - 测试数据库连接
@app.post("/api/test-database-connection")
async def test_database_connection(
    db_type: str = Form(...),
    host: str = Form(...),
    port: int = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    database: str = Form(...)
):
    """测试数据库连接"""
    try:
        from monitors.component import ComponentMonitor
        monitor = ComponentMonitor()
        config = {
            'target': db_type,
            'extra_config': {
                'host': host, 'port': port,
                'username': username, 'password': password,
                'database': database
            }
        }
        result = await monitor.check(config)
        return {
            "success": result.get('is_normal', False),
            "message": result.get('message', ''),
            "details": result.get('details', {})
        }
    except Exception as e:
        return {"success": False, "message": f"测试连接失败: {str(e)}"}

# API路由 - 报警数据
# 在 main.py 的 API 路由部分修改报警数据API

@app.get("/api/alerts")
async def get_alerts_api(
    start_date: str, 
    end_date: str, 
    page: int = 1, 
    per_page: int = 20
):
    """获取报警数据API - 支持分页"""
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        return {"success": False, "error": "日期格式错误"}
    
    try:
        # 计算总数
        count_query = '''
            SELECT COUNT(*) as total 
            FROM alert_data ad
            LEFT JOIN monitor_configs mc ON ad.config_id = mc.id
            WHERE ad.alert_time >= ? AND ad.alert_time <= ?
        '''
        
        total_count = execute_single(count_query, (start_dt, end_dt))['total']
        
        # 计算分页
        total_pages = (total_count + per_page - 1) // per_page
        offset = (page - 1) * per_page
        
        # 获取分页数据
        query = '''
            SELECT ad.*, mc.name as config_name 
            FROM alert_data ad
            LEFT JOIN monitor_configs mc ON ad.config_id = mc.id
            WHERE ad.alert_time >= ? AND ad.alert_time <= ?
            ORDER BY ad.alert_time DESC
            LIMIT ? OFFSET ?
        '''
        
        alerts_data = execute_query(query, (start_dt, end_dt, per_page, offset))

        # ===== 新增：为每条报警附加 Webhook 推送记录 =====
        alert_ids = [row['id'] for row in alerts_data]
        records_map = webhook_manager.get_push_records_for_alerts(alert_ids)
        alerts_data = [
            {**dict(row), 'webhook_records': records_map.get(row['id'], [])}
            for row in alerts_data
        ]
        # ==================================================        
        
        return {
            "success": True, 
            "data": alerts_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages
            }
        }
    except Exception as e:
        return {"success": False, "error": f"获取数据失败: {str(e)}"}    

# 在 main.py 的 API 路由部分添加

# API路由 - 邮箱测试
@app.post("/api/test-email")
async def test_email_config():
    """测试邮箱配置"""
    try:
        # 获取当前邮箱配置
        email_config = config_manager.get_email_config()
        if not email_config:
            return {"success": False, "error": "未配置邮箱信息"}

        # 获取一个有效的监控配置ID
        valid_config = execute_single('SELECT id FROM monitor_configs LIMIT 1')
        if not valid_config:
            return {"success": False, "error": "没有可用的监控配置"}
        
        test_config_id = valid_config['id']

        # 创建测试邮件内容
        test_subject = "监控系统 - 邮箱配置测试"
        test_body = f"""
        <html>
        <body>
            <h2>监控系统邮箱配置测试</h2>
            <p>这是一封测试邮件，用于验证监控系统的邮箱配置是否正确。</p>
            <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <p><strong>发送时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>SMTP服务器:</strong> {email_config['smtp_server']}:{email_config['smtp_port']}</p>
                <p><strong>发件人:</strong> {email_config['sender']}</p>
                <p><strong>收件人:</strong> {email_config['receivers']}</p>
            </div>
            <p>如果您收到了这封邮件，说明邮箱配置正确，监控系统的报警功能可以正常工作。</p>
            <hr>
            <small>此邮件由监控系统自动发送，请勿回复。</small>
        </body>
        </html>
        """
        
        # 创建临时报警记录用于测试
        test_alert = AlertRecord(
            config_id=test_config_id,  # 使用有效的 config_id
            monitor_type="test",
            alert_message="邮箱配置测试",
            alert_time=datetime.now()
        )

        # 在初始化之后启动，以免如果没有数据库报错
        alert_manager = AlertManager()         

        # 使用报警管理器发送测试邮件
        success = await alert_manager._send_email(test_subject, test_body)
        if success:
            # 记录测试成功
            test_alert.sent = True
            test_alert.receiver = email_config['receivers']
            alert_manager.save_alert_record(test_alert)
            
            return {
                "success": True, 
                "message": f"测试邮件发送成功！已发送到: {email_config['receivers']}"
            }
        else:
            # 记录测试失败
            test_alert.sent = False
            alert_manager.save_alert_record(test_alert)
            
            return {
                "success": False, 
                "error": "邮件发送失败，请检查邮箱配置和网络连接"
            }
            
    except Exception as e:
        return {"success": False, "error": f"测试过程中出现错误: {str(e)}"}
		

# 在 main.py 中添加项目名称相关的模型和API

class ProjectNameUpdate(BaseModel):
    project_name: str

# 添加项目名称 API
@app.get("/api/project-name")
async def get_project_name():
    """获取项目名称"""
    try:
        project_name = config_manager.get_project_name()
        return {"success": True, "project_name": project_name}
    except Exception as e:
        return {"success": False, "error": "获取项目名称失败"}

@app.put("/api/project-name")
async def update_project_name(config: ProjectNameUpdate):
    """更新项目名称"""
    try:
        success = config_manager.update_project_name(config.project_name)
        if success:
            return {"success": True, "message": "项目名称更新成功"}
        else:
            raise HTTPException(status_code=500, detail="更新项目名称失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail="更新项目名称失败")

# 修改获取通用上下文函数，添加用户信息
async def get_common_context(request: Request, current_user: dict = None):
    """获取通用模板上下文"""
    project_name = config_manager.get_project_name()
    context = {
        "request": request,
        "project_name": project_name,
        "current_year": datetime.now().year,
        "m_version": m_Version
    }
    
    if current_user:
        # 只传递用户名到模板，避免传递敏感信息
        context["current_user"] = {
            "username": current_user.get('username', 'Unknown')
        }    
    
    return context

# 全局异常处理
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP异常处理"""
    if exc.status_code == 401:
        # 对于页面请求，重定向到登录页面
        if not request.url.path.startswith("/api/"):
            return RedirectResponse(url="/login")
    
    # 其他HTTP异常保持原有行为
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理"""
    # 保持原有行为
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

# ==================== Webhook 推送配置 API ====================

class WebhookCreate(BaseModel):
    name: str
    url: str
    secret: str = ""
    enabled: bool = True

class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    secret: Optional[str] = None
    enabled: Optional[bool] = None

class WebhookTest(BaseModel):
    url: str
    secret: Optional[str] = ""

@app.get("/api/webhooks")
async def list_webhooks():
    """获取所有 Webhook 配置"""
    try:
        data = webhook_manager.get_all_webhooks()
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/webhooks")
async def create_webhook(config: WebhookCreate):
    """创建 Webhook 配置"""
    try:
        webhook_id = webhook_manager.create_webhook(config.dict())
        if webhook_id:
            return {"success": True, "data": {"id": webhook_id}}
        return {"success": False, "error": "创建失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.put("/api/webhooks/{webhook_id}")
async def update_webhook(webhook_id: int, config: WebhookUpdate):
    """更新 Webhook 配置"""
    try:
        success = webhook_manager.update_webhook(
            webhook_id, config.dict(exclude_unset=True)
        )
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: int):
    """删除 Webhook 配置"""
    try:
        success = webhook_manager.delete_webhook(webhook_id)
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/webhooks/test")
async def test_webhook(config: WebhookTest):
    """测试 Webhook 推送（与报警推送共用同一套签名逻辑）"""
    try:
        import httpx

        # 按 URL 识别平台，构建对应格式的测试消息
        platform = WebhookManager._detect_platform(config.url)
        test_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            project_name = config_manager.get_project_name()
        except Exception:
            project_name = "系统监测平台"

        if platform == 'wecom':
            test_payload = {
                "msgtype": "text",
                "text": {
                    "content": (
                        f"✅ 监控系统 Webhook 测试\n"
                        f"项目：{project_name}\n"
                        f"这是一条测试推送，收到即表示配置成功。\n"
                        f"时间：{test_time}"
                    )
                }
            }
        elif platform == 'dingtalk':
            test_payload = {
                "msgtype": "text",
                "text": {
                    "content": (
                        f"✅ 监控系统 Webhook 测试\n"
                        f"项目：{project_name}\n"
                        f"这是一条测试推送，收到即表示配置成功。\n"
                        f"时间：{test_time}"
                    )
                }
            }
        elif platform == 'feishu':
            test_payload = {
                "msg_type": "text",
                "content": {
                    "text": (
                        f"✅ 监控系统 Webhook 测试\n"
                        f"项目：{project_name}\n"
                        f"这是一条测试推送，收到即表示配置成功。\n"
                        f"时间：{test_time}"
                    )
                }
            }
        else:
            test_payload = {
                "event_type": "test",
                "project_name": project_name,
                "message": "这是一条来自监控系统的 Webhook 测试推送",
                "test_time": test_time
            }

        # ★ 关键：复用 WebhookManager 的公共签名方法，与 _push_single 完全一致
        body_bytes, headers = WebhookManager.build_signed_request(
            test_payload, config.secret or ""
        )
        logger.debug(
            f"[Webhook测试签名] url={config.url} "
            f"timestamp={headers.get('X-Webhook-Timestamp')} "
            f"body_len={len(body_bytes)} "
            f"signature={headers.get('X-Webhook-Signature-V2', '')[:16]}..."
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                config.url, content=body_bytes, headers=headers
            )

            if not (200 <= resp.status_code < 300):
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}"
                }

            # HTTP 200 也要检查业务错误码
            try:
                resp_json = resp.json()
            except Exception:
                resp_json = {}

            if platform == 'wecom':
                errcode = resp_json.get('errcode', 0)
                if errcode != 0:
                    return {
                        "success": False,
                        "error": (
                            f"企业微信返回错误 errcode={errcode}: "
                            f"{resp_json.get('errmsg', '未知错误')}"
                        )
                    }
            elif platform == 'dingtalk':
                errcode = resp_json.get('errcode', 0)
                if errcode != 0:
                    return {
                        "success": False,
                        "error": (
                            f"钉钉返回错误 errcode={errcode}: "
                            f"{resp_json.get('errmsg', '未知错误')}"
                        )
                    }
            elif platform == 'feishu':
                code = resp_json.get('code', 0)
                if code != 0:
                    return {
                        "success": False,
                        "error": (
                            f"飞书返回错误 code={code}: "
                            f"{resp_json.get('msg', '未知错误')}"
                        )
                    }

            return {
                "success": True,
                "message": f"推送成功 (HTTP {resp.status_code})"
            }

    except Exception as e:
        logger.error(f"测试 Webhook 异常: {e}")
        return {"success": False, "error": str(e)}

# ============================================================