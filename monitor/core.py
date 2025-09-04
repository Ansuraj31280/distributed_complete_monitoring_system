# 系统核心模块

import signal
import sys
import threading
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from loguru import logger

# 检查是否跳过数据库检查
skip_db_check = os.environ.get('SKIP_DB_CHECK', '').lower() == 'true'

if skip_db_check:
    logger.info("检测到SKIP_DB_CHECK环境变量，core模块将跳过数据库连接")
    from .config import get_config
    config = get_config()
    db_manager = None
    WebsiteModel = None
    task_scheduler = None
else:
    from .config import config
    from .database import db_manager, WebsiteModel
    from .scheduler import task_scheduler


class MonitorCore:
    """网页监控系统核心类"""
    
    def __init__(self, config_obj=None):
        self.config = config_obj or config
        self.is_running = False
        self.scheduler_thread = None
        self._setup_logging()
        self._setup_signal_handlers()
        logger.info("网页监控系统核心初始化完成")
    
    def _setup_logging(self):
        """设置日志配置"""
        logger.remove()  # 移除默认处理器
        
        # 检查config是否可用
        if self.config is None:
            # 使用默认配置
            logger.add(sys.stdout, level="INFO", colorize=True)
            logger.info("使用默认日志配置")
            return
        
        # 添加控制台日志
        logger.add(
            sys.stdout,
            level=self.config.logging.level,
            format=self.config.logging.format,
            colorize=True
        )
        
        # 添加文件日志
        logger.add(
            "logs/monitor_{time:YYYY-MM-DD}.log",
            level=self.config.logging.level,
            format=self.config.logging.format,
            rotation=self.config.logging.rotation,
            retention=self.config.logging.retention,
            compression=self.config.logging.compression,
            encoding="utf-8"
        )
        
        # 添加错误日志
        logger.add(
            "logs/error_{time:YYYY-MM-DD}.log",
            level="ERROR",
            format=self.config.logging.format,
            rotation=self.config.logging.rotation,
            retention=self.config.logging.retention,
            compression=self.config.logging.compression,
            encoding="utf-8"
        )
        
        logger.info("日志系统配置完成")
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"接收到信号 {signum}，开始优雅关闭...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def start(self):
        """启动监控系统"""
        if self.is_running:
            logger.warning("监控系统已经在运行中")
            return
        
        try:
            logger.info("正在启动网页监控系统...")
            
            # 检查系统依赖
            self._check_dependencies()
            
            # 初始化数据库
            self._initialize_database()
            
            # 启动任务调度器
            self._start_scheduler()
            
            self.is_running = True
            logger.info("网页监控系统启动成功")
            
        except Exception as e:
            logger.error(f"监控系统启动失败: {str(e)}")
            raise
    
    def stop(self):
        """停止监控系统"""
        if not self.is_running:
            logger.warning("监控系统未在运行")
            return
        
        try:
            logger.info("正在停止网页监控系统...")
            
            # 停止调度器
            self._stop_scheduler()
            
            # 关闭数据库连接
            db_manager.close()
            
            self.is_running = False
            logger.info("网页监控系统已停止")
            
        except Exception as e:
            logger.error(f"监控系统停止失败: {str(e)}")
            raise
    
    def _check_dependencies(self):
        """检查系统依赖"""
        logger.info("检查系统依赖...")
        
        if skip_db_check:
            logger.info("跳过数据库检查")
            return
        
        # 检查数据库连接
        try:
            with db_manager.get_session() as session:
                session.execute("SELECT 1")
            logger.info("PostgreSQL连接正常")
        except Exception as e:
            logger.error(f"PostgreSQL连接失败: {str(e)}")
            raise
        
        # 检查Redis连接
        if db_manager.is_redis_available():
            try:
                db_manager.get_redis().ping()
                logger.info("Redis连接正常")
            except Exception as e:
                logger.error(f"Redis连接失败: {str(e)}")
                logger.warning("Redis不可用，某些功能可能受限")
        else:
            logger.warning("Redis不可用，某些功能可能受限")
        
        logger.info("系统依赖检查完成")
    
    def _initialize_database(self):
        """初始化数据库"""
        if skip_db_check:
            logger.info("跳过数据库初始化")
            return
            
        logger.info("初始化数据库...")
        
        # 数据库表已在DatabaseManager初始化时创建
        # 这里可以添加初始数据或迁移逻辑
        
        logger.info("数据库初始化完成")
    
    def _start_scheduler(self):
        """启动任务调度器"""
        if skip_db_check:
            logger.info("跳过任务调度器启动")
            return
            
        logger.info("启动任务调度器...")
        
        # 在单独线程中启动调度器
        self.scheduler_thread = threading.Thread(
            target=task_scheduler.start_scheduler,
            daemon=True
        )
        self.scheduler_thread.start()
        
        logger.info("任务调度器已启动")
    
    def _stop_scheduler(self):
        """停止任务调度器"""
        logger.info("停止任务调度器...")
        
        # 这里可以添加停止调度器的逻辑
        # 由于使用了daemon线程，主程序退出时会自动停止
        
        logger.info("任务调度器已停止")
    
    def add_website(self, website_data: Dict[str, Any]) -> int:
        """添加网站监控"""
        if db_manager is None:
            logger.warning("数据库管理器不可用，无法添加网站")
            return -1
            
        try:
            # 验证必要字段
            required_fields = ['name', 'url']
            for field in required_fields:
                if field not in website_data:
                    raise ValueError(f"缺少必要字段: {field}")
            
            # 设置默认值
            website_data.setdefault('monitor_type', 'content')
            website_data.setdefault('priority', 'medium')
            website_data.setdefault('interval_minutes', 30)
            website_data.setdefault('enabled', True)
            website_data.setdefault('use_selenium', False)
            
            # 创建网站记录
            website_id = db_manager.create_website(website_data)
            
            logger.info(f"添加网站监控成功 - ID: {website_id}, URL: {website_data['url']}")
            
            # 立即调度一次监控任务
            if not skip_db_check and task_scheduler:
                task_scheduler.schedule_single_website(website_id)
            
            return website_id
            
        except Exception as e:
            logger.error(f"添加网站监控失败: {str(e)}")
            raise
    
    def remove_website(self, website_id: int) -> bool:
        """移除网站监控"""
        if db_manager is None:
            logger.warning("数据库管理器不可用，无法移除网站")
            return False
            
        try:
            with db_manager.get_session() as session:
                website = session.query(WebsiteModel).filter(
                    WebsiteModel.id == website_id
                ).first()
                
                if not website:
                    logger.warning(f"网站不存在 - ID: {website_id}")
                    return False
                
                # 禁用网站而不是删除
                website.enabled = False
                session.commit()
                
                logger.info(f"移除网站监控成功 - ID: {website_id}")
                return True
                
        except Exception as e:
            logger.error(f"移除网站监控失败 - ID: {website_id}, 错误: {str(e)}")
            raise
    
    def update_website(self, website_id: int, update_data: Dict[str, Any]) -> bool:
        """更新网站配置"""
        if db_manager is None:
            logger.warning("数据库管理器不可用，无法更新网站")
            return False
            
        try:
            with db_manager.get_session() as session:
                website = session.query(WebsiteModel).filter(
                    WebsiteModel.id == website_id
                ).first()
                
                if not website:
                    logger.warning(f"网站不存在 - ID: {website_id}")
                    return False
                
                # 更新字段
                for key, value in update_data.items():
                    if hasattr(website, key):
                        setattr(website, key, value)
                
                website.updated_at = datetime.now(timezone.utc)
                session.commit()
                
                logger.info(f"更新网站配置成功 - ID: {website_id}")
                return True
                
        except Exception as e:
            logger.error(f"更新网站配置失败 - ID: {website_id}, 错误: {str(e)}")
            raise
    
    def get_website_list(self) -> List[Dict[str, Any]]:
        """获取网站列表"""
        if db_manager is None:
            logger.warning("数据库管理器不可用，返回空列表")
            return []
            
        try:
            websites = db_manager.get_enabled_websites()
            
            result = []
            for website in websites:
                result.append({
                    'id': website.id,
                    'name': website.name,
                    'url': website.url,
                    'monitor_type': website.monitor_type,
                    'priority': website.priority,
                    'interval_minutes': website.interval_minutes,
                    'enabled': website.enabled,
                    'last_check_at': website.last_check_at.isoformat() if website.last_check_at else None,
                    'last_change_at': website.last_change_at.isoformat() if website.last_change_at else None,
                    'check_count': website.check_count,
                    'change_count': website.change_count
                })
            
            return result
            
        except Exception as e:
            logger.error(f"获取网站列表失败: {str(e)}")
            raise
    
    def get_website_status(self, website_id: int) -> Optional[Dict[str, Any]]:
        """获取网站状态"""
        if db_manager is None:
            logger.warning("数据库管理器不可用，无法获取网站状态")
            return None
            
        try:
            website = db_manager.get_website(website_id)
            if not website:
                return None
            
            # 获取最近的变化记录
            recent_changes = db_manager.get_recent_changes(website_id, limit=5)
            
            # 获取最新内容
            latest_content = db_manager.get_latest_content(website_id)
            
            return {
                'id': website.id,
                'name': website.name,
                'url': website.url,
                'monitor_type': website.monitor_type,
                'priority': website.priority,
                'interval_minutes': website.interval_minutes,
                'enabled': website.enabled,
                'last_check_at': website.last_check_at.isoformat() if website.last_check_at else None,
                'last_change_at': website.last_change_at.isoformat() if website.last_change_at else None,
                'check_count': website.check_count,
                'change_count': website.change_count,
                'recent_changes': [
                    {
                        'id': change.id,
                        'change_type': change.change_type,
                        'similarity_score': change.similarity_score,
                        'change_summary': change.change_summary,
                        'is_significant': change.is_significant,
                        'created_at': change.created_at.isoformat()
                    } for change in recent_changes
                ],
                'latest_content': {
                    'id': latest_content.id,
                    'content_length': latest_content.content_length,
                    'response_time': latest_content.response_time,
                    'status_code': latest_content.status_code,
                    'created_at': latest_content.created_at.isoformat()
                } if latest_content else None
            }
            
        except Exception as e:
            logger.error(f"获取网站状态失败 - ID: {website_id}, 错误: {str(e)}")
            raise
    
    def trigger_manual_check(self, website_id: int) -> str:
        """手动触发网站检查"""
        if db_manager is None:
            logger.warning("数据库管理器不可用，无法触发手动检查")
            return "error"
            
        try:
            # 验证网站存在
            website = db_manager.get_website(website_id)
            if not website:
                raise ValueError(f"网站不存在 - ID: {website_id}")
            
            # 调度监控任务
            if not skip_db_check and task_scheduler:
                task_id = task_scheduler.schedule_single_website(website_id)
            else:
                logger.warning("任务调度器不可用，无法调度监控任务")
                return "scheduler_unavailable"
            
            logger.info(f"手动触发网站检查 - 网站ID: {website_id}, 任务ID: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"手动触发网站检查失败 - 网站ID: {website_id}, 错误: {str(e)}")
            raise
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            # 获取队列状态
            if not skip_db_check and task_scheduler:
                queue_status = task_scheduler.get_queue_status()
                worker_status = task_scheduler.get_worker_status()
            else:
                queue_status = {'error': 'Task scheduler unavailable'}
                worker_status = {'error': 'Task scheduler unavailable'}
            
            # 获取网站统计
            with db_manager.get_session() as session:
                total_websites = session.query(db_manager.WebsiteModel).count()
                enabled_websites = session.query(db_manager.WebsiteModel).filter(
                    db_manager.WebsiteModel.enabled == True
                ).count()
                
                # 获取最近24小时的任务统计
                from datetime import timedelta
                yesterday = datetime.now(timezone.utc) - timedelta(days=1)
                
                recent_tasks = session.query(db_manager.TaskLogModel).filter(
                    db_manager.TaskLogModel.created_at >= yesterday
                ).count()
                
                failed_tasks = session.query(db_manager.TaskLogModel).filter(
                    db_manager.TaskLogModel.created_at >= yesterday,
                    db_manager.TaskLogModel.status == 'failed'
                ).count()
                
                recent_changes = session.query(db_manager.ChangeDetectionModel).filter(
                    db_manager.ChangeDetectionModel.created_at >= yesterday
                ).count()
            
            return {
                'system': {
                    'is_running': self.is_running,
                    'start_time': datetime.now(timezone.utc).isoformat()
                },
                'websites': {
                    'total': total_websites,
                    'enabled': enabled_websites,
                    'disabled': total_websites - enabled_websites
                },
                'tasks_24h': {
                    'total': recent_tasks,
                    'failed': failed_tasks,
                    'success_rate': (recent_tasks - failed_tasks) / recent_tasks * 100 if recent_tasks > 0 else 0
                },
                'changes_24h': recent_changes,
                'queue_status': queue_status,
                'worker_status': worker_status
            }
            
        except Exception as e:
            logger.error(f"获取系统状态失败: {str(e)}")
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        if not skip_db_check and task_scheduler:
            return task_scheduler.get_task_status(task_id)
        else:
            return {'error': 'Task scheduler unavailable'}
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if not skip_db_check and task_scheduler:
            return task_scheduler.cancel_task(task_id)
        else:
            logger.warning("任务调度器不可用，无法取消任务")
            return False
    
    def run_forever(self):
        """持续运行监控系统"""
        try:
            self.start()
            
            logger.info("监控系统正在运行，按 Ctrl+C 停止...")
            
            # 保持主线程运行
            while self.is_running:
                import time
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("接收到中断信号")
        except Exception as e:
            logger.error(f"监控系统运行异常: {str(e)}")
        finally:
            self.stop()


# 全局监控核心实例
monitor_core = MonitorCore()