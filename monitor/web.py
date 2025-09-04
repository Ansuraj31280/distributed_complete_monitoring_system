# Web管理界面

import json
import asyncio
import os
import psutil
import platform
import time
import yaml
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from loguru import logger
from .config import get_config

# 全局变量，用于标记是否跳过数据库检查
skip_db_check = os.environ.get('SKIP_DB_CHECK', '').lower() == 'true'

# 初始化配置
config = get_config()

# 预先设置数据库相关变量
db_manager = None
WebsiteModel = None

if skip_db_check:
    logger.info("检测到SKIP_DB_CHECK环境变量，将跳过数据库连接")
    # 在跳过数据库检查模式下，不导入数据库模块
    db_manager = None
    WebsiteModel = None
else:
    # 导入数据库相关模块
    try:
        from .database import DatabaseManager, WebsiteModel
        db_manager = DatabaseManager(skip_db_check=False)
    except Exception as e:
        logger.warning(f"数据库模块导入失败: {e}")
        db_manager = None
        WebsiteModel = None

# 确保在db_manager为None时不会出错的辅助函数
def safe_db_operation(func, *args, **kwargs):
    """安全执行数据库操作的包装函数"""
    if db_manager is None:
        logger.warning(f"数据库管理器不可用，无法执行操作: {func.__name__}")
        return None
    return func(*args, **kwargs)

# 确保在db_manager为None时不会出错的辅助函数
def safe_db_operation(func, *args, **kwargs):
    """安全执行数据库操作的包装函数"""
    if db_manager is None:
        logger.warning(f"数据库管理器不可用，无法执行操作: {func.__name__}")
        return None
    return func(*args, **kwargs)

# 尝试导入SQLAlchemy，如果失败则设置为None
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
except Exception as e:
    logger.warning(f"导入SQLAlchemy模块失败: {e}")
    create_engine = None
    sessionmaker = None
    text = None

# 延迟导入core和tasks模块，避免在跳过数据库检查时出错
if not skip_db_check:
    from .core import MonitorCore
    from .tasks import (
        manual_check_website, 
        get_task_status, 
        get_queue_status,
        batch_fetch_websites
    )
else:
    MonitorCore = None
    manual_check_website = None
    get_task_status = None
    get_queue_status = None
    batch_fetch_websites = None


# 创建Flask应用
app = Flask(__name__, 
           template_folder='templates',
           static_folder='static')

# 延迟初始化secret_key
if not skip_db_check:
    try:
        config = get_config()
        app.secret_key = config.web.secret_key
    except Exception as e:
        logger.warning(f"获取配置失败，使用默认secret_key: {e}")
        app.secret_key = 'dev-secret-key-for-skip-db-mode'
else:
    app.secret_key = 'dev-secret-key-for-skip-db-mode'
app.config['JSON_AS_ASCII'] = False

# 启用CORS
CORS(app)

# 添加一个简单的健康检查API
@app.route('/api/health', methods=['GET'])
def api_health_check():
    """健康检查API，不依赖数据库"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'db_available': db_manager is not None,
        'skip_db_check': skip_db_check
    })

# 全局变量
monitor_core = None


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.is_json:
                return jsonify({'error': '需要登录'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def load_user(user_id):
    """加载用户"""
    if db_manager is None:
        # 如果数据库管理器不可用，返回None
        logger.warning(f"数据库管理器不可用，无法加载用户ID: {user_id}")
        return None
    try:
        return db_manager.get_user_by_id(user_id)
    except Exception as e:
        logger.error(f"加载用户失败: {str(e)}")
        return None


def admin_required(f):
    """管理员权限验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in') or session.get('role') != 'admin':
            if request.is_json:
                return jsonify({'error': '需要管理员权限'}), 403
            flash('需要管理员权限', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# 系统信息获取函数
def get_system_uptime():
    """获取系统运行时间"""
    try:
        if hasattr(psutil, 'boot_time'):
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            return f"{days}天{hours}小时{minutes}分钟"
        return "未知"
    except Exception as e:
        logger.error(f"获取系统运行时间失败: {e}")
        return "未知"


def get_cpu_usage():
    """获取CPU使用率"""
    try:
        return f"{psutil.cpu_percent(interval=0.1)}%"
    except Exception as e:
        logger.error(f"获取CPU使用率失败: {e}")
        return "未知"


def get_memory_usage():
    """获取内存使用情况"""
    try:
        memory = psutil.virtual_memory()
        return {
            'memory_used': memory.used,
            'memory_total': memory.total,
            'memory_percent': memory.percent
        }
    except Exception as e:
        logger.error(f"获取内存使用情况失败: {e}")
        return {
            'memory_used': 0,
            'memory_total': 0,
            'memory_percent': 0
        }


def get_disk_usage():
    """获取磁盘使用情况"""
    try:
        disk = psutil.disk_usage('/')
        return {
            'disk_used': disk.used,
            'disk_total': disk.total,
            'disk_percent': disk.percent
        }
    except Exception as e:
        logger.error(f"获取磁盘使用情况失败: {e}")
        return {
            'disk_used': 0,
            'disk_total': 0,
            'disk_percent': 0
        }


# 删除重复的admin_required装饰器定义
# 注意：确保已安装psutil包，可以使用 pip install psutil


# 认证路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 简单的用户验证（实际项目中应该使用数据库）
        config = get_config() if not skip_db_check else None
        admin_username = config.web.admin_username if config else 'admin'
        admin_password = config.web.admin_password if config else 'admin123'
        if username == admin_username and password == admin_password:
            session['logged_in'] = True
            session['username'] = username
            session['role'] = 'admin'
            flash('登录成功', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """登出"""
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('login'))


# 主要页面路由
@app.route('/')
@login_required
def dashboard():
    """仪表板页面"""
    try:
        # 检查数据库管理器是否可用
        if db_manager is None:
            logger.warning("数据库管理器不可用，显示空仪表板")
            flash('数据库连接不可用，显示空仪表板', 'warning')
            return render_template('dashboard.html', stats={}, recent_changes=[], system_status={})
            
        # 获取统计信息
        stats = {
            'total_websites': db_manager.get_total_websites_count(),
            'active_websites': db_manager.get_active_websites_count(),
            'total_checks': db_manager.get_total_checks_count(),
            'recent_changes': db_manager.get_recent_changes_count(hours=24)
        }
        
        # 获取最近的变化
        recent_changes = db_manager.get_recent_changes(limit=10)
        
        # 获取系统状态
        system_status = db_manager.get_latest_system_metrics()
        
        return render_template('dashboard.html', 
                             stats=stats, 
                             recent_changes=recent_changes,
                             system_status=system_status)
    except Exception as e:
        logger.error(f"仪表板页面加载失败: {str(e)}")
        flash('仪表板加载失败', 'error')
        return render_template('dashboard.html', stats={}, recent_changes=[], system_status={})


@app.route('/websites')
@login_required
def websites():
    """网站管理页面"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        websites = db_manager.get_websites_paginated(page, per_page)
        
        return render_template('websites.html', websites=websites)
    except Exception as e:
        logger.error(f"网站管理页面加载失败: {str(e)}")
        flash('网站列表加载失败', 'error')
        return render_template('websites.html', websites=[])


@app.route('/website/<int:website_id>')
@login_required
def website_detail(website_id):
    """网站详情页面"""
    try:
        website = db_manager.get_website(website_id)
        if not website:
            flash('网站不存在', 'error')
            return redirect(url_for('websites'))
        
        # 获取最近的内容
        recent_contents = db_manager.get_latest_contents(website_id, limit=10)
        
        # 获取变化历史
        change_history = db_manager.get_change_history(website_id, limit=20)
        
        # 获取统计信息
        stats = db_manager.get_website_statistics(website_id)
        
        return render_template('website_detail.html', 
                             website=website,
                             recent_contents=recent_contents,
                             change_history=change_history,
                             stats=stats)
    except Exception as e:
        logger.error(f"网站详情页面加载失败: {str(e)}")
        flash('网站详情加载失败', 'error')
        return redirect(url_for('websites'))


# 任务页面缓存
_tasks_page_cache = {
    'data': None,
    'last_update': 0,
    'cache_ttl': 5  # 缓存有效期（秒）
}

@app.route('/tasks')
@login_required
def tasks():
    """任务管理页面"""
    global _tasks_page_cache
    
    try:
        current_time = time.time()
        
        # 如果缓存有效，直接使用缓存数据
        if (_tasks_page_cache['data'] is not None and 
            current_time - _tasks_page_cache['last_update'] < _tasks_page_cache['cache_ttl']):
            cache_data = _tasks_page_cache['data']
            return render_template('tasks.html', **cache_data)
        
        # 获取队列状态（已经有缓存机制）
        queue_status = get_queue_status()
        
        # 获取最近的任务日志
        recent_tasks = db_manager.get_recent_task_logs(limit=50)
        
        # 创建任务统计信息 - 优化计算方式
        active_count = 0
        scheduled_count = 0
        reserved_count = 0
        
        # 使用更高效的方式计算任务数量
        if queue_status and 'active_tasks' in queue_status and queue_status['active_tasks']:
            active_count = sum(len(tasks) if tasks else 0 for worker, tasks in queue_status['active_tasks'].items())
                
        if queue_status and 'scheduled_tasks' in queue_status and queue_status['scheduled_tasks']:
            scheduled_count = sum(len(tasks) if tasks else 0 for worker, tasks in queue_status['scheduled_tasks'].items())
                
        if queue_status and 'reserved_tasks' in queue_status and queue_status['reserved_tasks']:
            reserved_count = sum(len(tasks) if tasks else 0 for worker, tasks in queue_status['reserved_tasks'].items())
                
        task_stats = {
            'running': active_count,
            'pending': scheduled_count + reserved_count,
            'completed': 0,  # 无法从队列状态获取已完成任务数
            'failed': 0      # 无法从队列状态获取失败任务数
        }
        
        # 创建队列统计信息 - 优化计算方式
        queue_stats = {}
        if queue_status and 'worker_stats' in queue_status and queue_status['worker_stats']:
            # 预处理队列统计信息
            for worker_name, stats in queue_status['worker_stats'].items():
                if not stats or 'queues' not in stats:
                    continue
                    
                for queue_name, queue_info in stats['queues'].items():
                    if queue_name not in queue_stats:
                        queue_stats[queue_name] = {
                            'length': 0,
                            'workers': 0
                        }
                    queue_stats[queue_name]['length'] += queue_info.get('messages', 0)
                    queue_stats[queue_name]['workers'] += 1
        
        # 更新缓存
        page_data = {
            'queue_status': queue_status,
            'queue_stats': queue_stats,
            'recent_tasks': recent_tasks,
            'task_stats': task_stats
        }
        _tasks_page_cache['data'] = page_data
        _tasks_page_cache['last_update'] = current_time
        
        return render_template('tasks.html', **page_data)
    except Exception as e:
        logger.error(f"任务管理页面加载失败: {str(e)}")
        flash('任务管理页面加载失败', 'error')
        
        # 如果有缓存数据，尝试使用缓存数据
        if _tasks_page_cache['data'] is not None:
            logger.info("使用缓存数据显示任务管理页面")
            return render_template('tasks.html', **_tasks_page_cache['data'])
        
        # 无缓存数据时显示空页面
        empty_data = {
            'queue_status': {}, 
            'queue_stats': {}, 
            'recent_tasks': [], 
            'task_stats': {'running': 0, 'pending': 0, 'completed': 0, 'failed': 0}
        }
        return render_template('tasks.html', **empty_data)


@app.route('/settings')
@admin_required
def settings():
    """系统设置页面"""
    # 创建系统信息对象
    memory_info = get_memory_usage()
    disk_info = get_disk_usage()
    system_info = {
        'status': '运行中',
        'uptime': get_system_uptime(),
        'cpu_usage': get_cpu_usage(),
        'version': '1.0.0',
        **memory_info,
        **disk_info
    }
    return render_template('settings.html', config=config, system_info=system_info)


@app.route('/api/settings/general', methods=['POST'])
@admin_required
def api_settings_general():
    """保存常规设置API"""
    try:
        data = request.get_json()
        
        # 验证必需字段
        required_fields = ['system_name', 'default_check_interval', 'max_retries', 'timezone', 'log_level']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'缺少必需字段: {field}'}), 400
        
        # 更新配置文件中的常规设置
        config_data = config.get_config()
        
        # 更新系统名称
        config_data['system_name'] = data['system_name']
        
        # 更新默认检查间隔
        config_data['default_check_interval'] = data['default_check_interval']
        
        # 更新最大重试次数
        config_data['max_retries'] = data['max_retries']
        
        # 更新时区
        config_data['timezone'] = data['timezone']
        
        # 更新日志级别
        if 'logging' not in config_data:
            config_data['logging'] = {}
        config_data['logging']['level'] = data['log_level']
        
        # 更新指标收集设置
        config_data['enable_metrics'] = data.get('enable_metrics', False)
        
        # 设置跳过数据库检查标志
        global skip_db_check
        skip_db_check = True
        logger.info("设置跳过数据库检查标志为True")
        
        # 保存配置前确保所有必要的配置节点存在
        if 'database' not in config_data:
            config_data['database'] = {}
        if 'security' not in config_data:
            config_data['security'] = {}
        if 'notification' not in config_data:
            config_data['notification'] = {}
        
        # 保存配置
        with open(config.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        # 重新加载配置
        config.reload()
        logger.info("配置已重新加载")
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"保存常规设置API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# API路由
@app.route('/api/test/database', methods=['POST'])
@admin_required
def api_test_database():
    """测试数据库连接API"""
    try:
        data = request.get_json()
        
        # 验证必需字段
        required_fields = ['host', 'port', 'name', 'user', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'缺少必需字段: {field}'}), 400
        
        # 构建数据库URL
        db_url = f"postgresql://{data['user']}:{data['password']}@{data['host']}:{data['port']}/{data['name']}"
        
        # 尝试连接数据库
        try:
            # 导入SQLAlchemy引擎
            from sqlalchemy import create_engine
            
            engine = create_engine(db_url, connect_args={'connect_timeout': 5})
            connection = engine.connect()
            connection.close()
            engine.dispose()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
            
    except Exception as e:
        logger.error(f"测试数据库连接API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/test/redis', methods=['POST'])
@admin_required
def api_test_redis():
    """测试Redis连接API"""
    try:
        data = request.get_json()
        
        # 验证必需字段
        required_fields = ['host', 'port', 'db']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'缺少必需字段: {field}'}), 400
        
        # 尝试连接Redis
        try:
            password = data.get('password', None)
            redis_client = redis.Redis(
                host=data['host'],
                port=int(data['port']),
                db=int(data['db']),
                password=password,
                socket_timeout=5
            )
            # 测试连接
            redis_client.ping()
            redis_client.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
            
    except Exception as e:
        logger.error(f"测试Redis连接API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/info', methods=['GET'])
@admin_required
def api_system_info():
    """获取系统信息API"""
    try:
        # 获取系统信息
        memory_info = get_memory_usage()
        disk_info = get_disk_usage()
        
        system_info = {
            'status': '运行中',
            'uptime': get_system_uptime(),
            'cpu_usage': get_cpu_usage(),
            'version': '1.0.0',
            **memory_info,
            **disk_info
        }
        
        # 获取数据库状态
        try:
            db_status = '正常'
            with db.engine.connect() as connection:
                connection.execute(text('SELECT 1'))
        except Exception:
            db_status = '异常'
            
        # 获取Redis状态
        try:
            redis_status = '正常'
            redis_client.ping()
        except Exception:
            redis_status = '异常'
            
        # 获取Celery状态
        try:
            celery_status = '正常'
            i = celery_app.control.inspect()
            if not i.ping():
                celery_status = '异常'
        except Exception:
            celery_status = '异常'
            
        # 添加到系统信息
        system_info['database_status'] = db_status
        system_info['redis_status'] = redis_status
        system_info['celery_status'] = celery_status
        
        return jsonify({'success': True, 'data': system_info})
        
    except Exception as e:
        logger.error(f"获取系统信息API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/settings/security', methods=['POST'])
@admin_required
def api_settings_security():
    """保存安全设置API"""
    try:
        data = request.get_json()
        
        # 验证必需字段
        required_fields = ['api_rate_limit_per_minute', 'https_only', 'enable_csrf_protection']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'缺少必需字段: {field}'}), 400
        
        # 更新配置文件中的安全设置
        config_data = config.get_config()
        
        # 确保security部分存在
        if 'security' not in config_data:
            config_data['security'] = {}
            
        # 更新API速率限制
        config_data['security']['api_rate_limit_per_minute'] = data['api_rate_limit_per_minute']
        
        # 更新允许的IP地址
        config_data['security']['allowed_ips'] = data.get('allowed_ips', [])
        
        # 更新HTTPS设置
        config_data['security']['https_only'] = data['https_only']
        
        # 更新CSRF保护设置
        config_data['security']['enable_csrf_protection'] = data['enable_csrf_protection']
        
        # 保存配置
        with open(config.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        # 重新加载配置
        config.reload()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"保存安全设置API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/settings/database', methods=['POST'])
@admin_required
def api_settings_database():
    """保存数据库设置API"""
    try:
        data = request.get_json()
        
        # 验证必需字段
        required_fields = ['host', 'port', 'name', 'user', 'password', 'pool_size']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'缺少必需字段: {field}'}), 400
        
        # 更新配置文件中的数据库设置
        config_data = config.get_config()
        
        # 确保database部分存在
        if 'database' not in config_data:
            config_data['database'] = {}
            
        # 更新数据库设置
        config_data['database']['host'] = data['host']
        config_data['database']['port'] = data['port']
        config_data['database']['name'] = data['name']
        config_data['database']['user'] = data['user']
        config_data['database']['password'] = data['password']
        config_data['database']['pool_size'] = data['pool_size']
        
        # 保存配置
        with open(config.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        # 重新加载配置
        config.reload()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"保存数据库设置API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/settings/celery', methods=['POST'])
@admin_required
def api_settings_celery():
    """保存Celery任务队列设置API"""
    try:
        data = request.get_json()
        
        # 验证必需字段
        required_fields = ['redis_host', 'redis_port', 'redis_db', 'concurrency', 'task_timeout', 'result_expires']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'缺少必需字段: {field}'}), 400
        
        # 更新配置文件中的Celery设置
        config_data = config.get_config()
        
        # 确保celery部分存在
        if 'celery' not in config_data:
            config_data['celery'] = {}
            
        # 更新Redis连接设置
        config_data['celery']['redis_host'] = data['redis_host']
        config_data['celery']['redis_port'] = data['redis_port']
        config_data['celery']['redis_db'] = data['redis_db']
        
        # 更新Redis密码（如果提供）
        if 'redis_password' in data and data['redis_password']:
            config_data['celery']['redis_password'] = data['redis_password']
        elif 'redis_password' in config_data['celery']:
            # 如果未提供密码但配置中存在，则删除它
            del config_data['celery']['redis_password']
        
        # 更新工作进程设置
        config_data['celery']['concurrency'] = data['concurrency']
        config_data['celery']['task_timeout'] = data['task_timeout']
        config_data['celery']['result_expires'] = data['result_expires']
        
        # 保存配置
        with open(config.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        # 重新加载配置
        config.reload()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"保存Celery设置API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/settings/notification', methods=['POST'])
@admin_required
def api_settings_notification():
    """保存通知设置API"""
    try:
        data = request.get_json()
        
        # 验证必需字段
        required_fields = ['email_enabled', 'webhook_enabled']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'缺少必需字段: {field}'}), 400
        
        # 更新配置文件中的通知设置
        config_data = config.get_config()
        
        # 确保notification部分存在
        if 'notification' not in config_data:
            config_data['notification'] = {}
            
        # 更新邮件通知设置
        config_data['notification']['email_enabled'] = data['email_enabled']
        if data['email_enabled']:
            # 验证邮件设置字段
            email_fields = ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password', 'sender_email', 'recipient_emails']
            for field in email_fields:
                if field not in data:
                    return jsonify({'success': False, 'error': f'启用邮件通知时缺少必需字段: {field}'}), 400
                    
            # 更新邮件设置
            config_data['notification']['smtp_server'] = data['smtp_server']
            config_data['notification']['smtp_port'] = data['smtp_port']
            config_data['notification']['smtp_username'] = data['smtp_username']
            config_data['notification']['smtp_password'] = data['smtp_password']
            config_data['notification']['sender_email'] = data['sender_email']
            config_data['notification']['recipient_emails'] = data['recipient_emails']
            config_data['notification']['smtp_use_tls'] = data.get('smtp_use_tls', False)
            
        # 更新Webhook通知设置
        config_data['notification']['webhook_enabled'] = data['webhook_enabled']
        if data['webhook_enabled']:
            # 验证Webhook设置字段
            if 'webhook_url' not in data:
                return jsonify({'success': False, 'error': '启用Webhook通知时缺少必需字段: webhook_url'}), 400
                
            # 更新Webhook设置
            config_data['notification']['webhook_url'] = data['webhook_url']
            config_data['notification']['webhook_custom_headers'] = data.get('webhook_custom_headers', {})
            
        # 保存配置
        with open(config.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        # 重新加载配置
        config.reload()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"保存通知设置API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/settings/monitoring', methods=['POST'])
@admin_required
def api_settings_monitoring():
    """保存监控设置API"""
    try:
        data = request.get_json()
        
        # 验证必需字段
        required_fields = ['content_check_enabled', 'screenshot_enabled', 'performance_monitoring_enabled']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'缺少必需字段: {field}'}), 400
        
        # 更新配置文件中的监控设置
        config_data = config.get_config()
        
        # 确保monitoring部分存在
        if 'monitoring' not in config_data:
            config_data['monitoring'] = {}
            
        # 更新内容检查设置
        config_data['monitoring']['content_check_enabled'] = data['content_check_enabled']
        if data['content_check_enabled']:
            # 更新内容检查相关设置
            config_data['monitoring']['content_check_method'] = data.get('content_check_method', 'keywords')
            config_data['monitoring']['content_diff_threshold'] = data.get('content_diff_threshold', 0.1)
            
        # 更新截图设置
        config_data['monitoring']['screenshot_enabled'] = data['screenshot_enabled']
        if data['screenshot_enabled']:
            # 更新截图相关设置
            config_data['monitoring']['screenshot_storage_days'] = data.get('screenshot_storage_days', 30)
            config_data['monitoring']['screenshot_comparison_enabled'] = data.get('screenshot_comparison_enabled', True)
            
        # 更新性能监控设置
        config_data['monitoring']['performance_monitoring_enabled'] = data['performance_monitoring_enabled']
        if data['performance_monitoring_enabled']:
            # 更新性能监控相关设置
            config_data['monitoring']['performance_timeout_threshold'] = data.get('performance_timeout_threshold', 10)
            config_data['monitoring']['collect_resource_timing'] = data.get('collect_resource_timing', True)
            
        # 保存配置
        with open(config.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        # 重新加载配置
        config.reload()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"保存监控设置API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/websites', methods=['GET'])
@login_required
def api_get_websites():
    """获取网站列表API"""
    try:
        # 检查是否在跳过数据库检查模式
        if skip_db_check or db_manager is None:
            return jsonify({
                'success': True,
                'data': [],
                'message': '当前处于跳过数据库检查模式，无法获取网站列表'
            })
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        
        websites = db_manager.search_websites(search, page, per_page)
        
        return jsonify({
            'success': True,
            'data': [{
                'id': w.id,
                'name': w.name,
                'url': w.url,
                'enabled': w.enabled,
                'check_interval': w.check_interval,
                'last_check_at': w.last_check_at.isoformat() if w.last_check_at else None,
                'created_at': w.created_at.isoformat()
            } for w in websites]
        })
    except Exception as e:
        logger.error(f"获取网站列表API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/websites', methods=['POST'])
@admin_required
def api_create_website():
    """创建网站API"""
    try:
        # 检查是否在跳过数据库检查模式
        if skip_db_check or monitor_core is None:
            return jsonify({
                'success': False, 
                'error': '当前处于跳过数据库检查模式，无法创建网站'
            }), 503
        
        data = request.get_json()
        
        # 验证必需字段
        required_fields = ['name', 'url']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'缺少必需字段: {field}'}), 400
        
        # 创建网站
        website_id = monitor_core.add_website(
            name=data['name'],
            url=data['url'],
            check_interval=data.get('check_interval', 60),
            selector=data.get('selector'),
            xpath=data.get('xpath'),
            headers=data.get('headers'),
            cookies=data.get('cookies'),
            user_agent=data.get('user_agent'),
            proxy=data.get('proxy'),
            use_selenium=data.get('use_selenium', False),
            detection_algorithm=data.get('detection_algorithm', 'hash'),
            notification_enabled=data.get('notification_enabled', True),
            notification_threshold=data.get('notification_threshold', 0.1),
            notification_emails=data.get('notification_emails', []),
            webhook_urls=data.get('webhook_urls', []),
            dingtalk_webhooks=data.get('dingtalk_webhooks', [])
        )
        
        return jsonify({
            'success': True,
            'data': {'website_id': website_id}
        })
        
    except Exception as e:
        logger.error(f"创建网站API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/websites/<int:website_id>', methods=['PUT'])
@admin_required
def api_update_website(website_id):
    """更新网站API"""
    try:
        # 检查是否在跳过数据库检查模式
        if skip_db_check or monitor_core is None:
            return jsonify({
                'success': False, 
                'error': '当前处于跳过数据库检查模式，无法更新网站'
            }), 503
        
        data = request.get_json()
        
        success = monitor_core.update_website(website_id, data)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '网站不存在'}), 404
            
    except Exception as e:
        logger.error(f"更新网站API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/websites/<int:website_id>', methods=['DELETE'])
@admin_required
def api_delete_website(website_id):
    """删除网站API"""
    try:
        # 检查是否在跳过数据库检查模式
        if skip_db_check or monitor_core is None:
            return jsonify({
                'success': False, 
                'error': '当前处于跳过数据库检查模式，无法删除网站'
            }), 503
        
        success = monitor_core.remove_website(website_id)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '网站不存在'}), 404
            
    except Exception as e:
        logger.error(f"删除网站API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/websites/<int:website_id>/check', methods=['POST'])
@login_required
def api_manual_check_website(website_id):
    """手动检查网站API"""
    try:
        # 检查是否在跳过数据库检查模式
        if skip_db_check or db_manager is None:
            return jsonify({
                'success': False, 
                'error': '当前处于跳过数据库检查模式，无法手动检查网站'
            }), 503
        
        # 验证网站存在
        website = db_manager.get_website(website_id)
        if not website:
            return jsonify({'success': False, 'error': '网站不存在'}), 404
        
        # 提交手动检查任务
        result = manual_check_website.delay(website_id)
        
        return jsonify({
            'success': True,
            'data': {
                'task_id': result.id,
                'website_id': website_id
            }
        })
        
    except Exception as e:
        logger.error(f"手动检查网站API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/websites/<int:website_id>/toggle', methods=['POST'])
@admin_required
def api_toggle_website(website_id):
    """启用/禁用网站API"""
    try:
        # 检查是否在跳过数据库检查模式
        if skip_db_check or db_manager is None or monitor_core is None:
            return jsonify({
                'success': False, 
                'error': '当前处于跳过数据库检查模式，无法切换网站状态'
            }), 503
        
        website = db_manager.get_website(website_id)
        if not website:
            return jsonify({'success': False, 'error': '网站不存在'}), 404
        
        # 切换启用状态
        new_enabled = not website.enabled
        success = monitor_core.update_website(website_id, {'enabled': new_enabled})
        
        if success:
            return jsonify({
                'success': True,
                'data': {'enabled': new_enabled}
            })
        else:
            return jsonify({'success': False, 'error': '更新失败'}), 500
            
    except Exception as e:
        logger.error(f"切换网站状态API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tasks/<task_id>/status', methods=['GET'])
@login_required
def api_get_task_status(task_id):
    """获取任务状态API"""
    try:
        status = get_task_status(task_id)
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        logger.error(f"获取任务状态API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# API队列状态缓存
_api_queue_status_cache = {
    'data': None,
    'last_update': 0,
    'cache_ttl': 5  # 缓存有效期（秒）
}

@app.route('/api/queue/status', methods=['GET'])
@login_required
def api_get_queue_status():
    """获取队列状态API"""
    global _api_queue_status_cache
    
    try:
        current_time = time.time()
        
        # 如果缓存有效，直接使用缓存数据
        if (_api_queue_status_cache['data'] is not None and 
            current_time - _api_queue_status_cache['last_update'] < _api_queue_status_cache['cache_ttl']):
            return jsonify({
                'success': True,
                'data': _api_queue_status_cache['data']
            })
        
        # 获取队列状态（已经有缓存机制）
        status = get_queue_status()
        
        # 更新缓存
        _api_queue_status_cache['data'] = status
        _api_queue_status_cache['last_update'] = current_time
        
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        logger.error(f"获取队列状态API失败: {str(e)}")
        
        # 如果有缓存数据，尝试使用缓存数据
        if _api_queue_status_cache['data'] is not None:
            logger.info("使用缓存数据返回队列状态API")
            return jsonify({
                'success': True,
                'data': _api_queue_status_cache['data']
            })
            
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/statistics', methods=['GET'])
@login_required
def api_get_statistics():
    """获取统计信息API"""
    try:
        days = request.args.get('days', 7, type=int)
        
        stats = {
            'total_websites': db_manager.get_total_websites_count(),
            'active_websites': db_manager.get_active_websites_count(),
            'total_checks': db_manager.get_total_checks_count(),
            'recent_changes': db_manager.get_recent_changes_count(hours=24),
            'daily_stats': db_manager.get_daily_statistics(days)
        }
        
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"获取统计信息API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/websites/<int:website_id>/history', methods=['GET'])
@login_required
def api_get_website_history(website_id):
    """获取网站历史API"""
    try:
        limit = request.args.get('limit', 50, type=int)
        
        # 获取内容历史
        contents = db_manager.get_latest_contents(website_id, limit)
        
        # 获取变化历史
        changes = db_manager.get_change_history(website_id, limit)
        
        return jsonify({
            'success': True,
            'data': {
                'contents': [{
                    'id': c.id,
                    'content_hash': c.content_hash,
                    'content_length': c.content_length,
                    'response_time': c.response_time,
                    'status_code': c.status_code,
                    'error_message': c.error_message,
                    'created_at': c.created_at.isoformat()
                } for c in contents],
                'changes': [{
                    'id': ch.id,
                    'change_type': ch.change_type,
                    'change_score': ch.change_score,
                    'diff_summary': ch.diff_summary,
                    'created_at': ch.created_at.isoformat()
                } for ch in changes]
            }
        })
    except Exception as e:
        logger.error(f"获取网站历史API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/batch/check', methods=['POST'])
@admin_required
def api_batch_check_websites():
    """批量检查网站API"""
    try:
        data = request.get_json()
        website_ids = data.get('website_ids', [])
        
        if not website_ids:
            return jsonify({'success': False, 'error': '没有指定网站ID'}), 400
        
        # 提交批量检查任务
        result = batch_fetch_websites.delay(website_ids)
        
        return jsonify({
            'success': True,
            'data': {
                'task_id': result.id,
                'website_count': len(website_ids)
            }
        })
        
    except Exception as e:
        logger.error(f"批量检查网站API失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# 错误处理
@app.errorhandler(404)
def not_found(error):
    if request.is_json:
        return jsonify({'error': '页面不存在'}), 404
    return render_template('error.html', error='页面不存在'), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"内部服务器错误: {str(error)}")
    if request.is_json:
        return jsonify({'error': '内部服务器错误'}), 500
    return render_template('error.html', error='内部服务器错误'), 500


# 模板过滤器
@app.template_filter('datetime')
def datetime_filter(dt):
    """日期时间格式化过滤器"""
    if dt is None:
        return '未知'
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return dt
    return dt.strftime('%Y-%m-%d %H:%M:%S')


@app.template_filter('timedelta')
def timedelta_filter(dt):
    """时间差格式化过滤器"""
    if dt is None:
        return '未知'
    
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return dt
    
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    diff = now - dt
    
    if diff.days > 0:
        return f'{diff.days}天前'
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f'{hours}小时前'
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f'{minutes}分钟前'
    else:
        return '刚刚'


@app.template_filter('filesize')
def filesize_filter(size):
    """文件大小格式化过滤器"""
    if size is None:
        return '0 B'
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f'{size:.1f} {unit}'
        size /= 1024.0
    return f'{size:.1f} TB'


def create_app(monitor_core_instance):
    """创建Flask应用"""
    global monitor_core
    monitor_core = monitor_core_instance
    
    return app


def run_web_server():
    """运行Web服务器"""
    try:
        logger.info(f"启动Web服务器 - 地址: {config.web.host}:{config.web.port}")
        
        app.run(
            host=config.web.host,
            port=config.web.port,
            debug=config.web.debug,
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"Web服务器启动失败: {str(e)}")
        raise