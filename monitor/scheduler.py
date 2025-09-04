# 任务调度器模块

import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from celery import Celery
from celery.schedules import crontab
from loguru import logger
import psutil
import socket
from .config import config
from .database import db_manager, WebsiteModel


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, config=None):
        self.config = config
        self.celery_app = self._create_celery_app()
        self.hostname = socket.gethostname()
        self._register_tasks()
        self._setup_periodic_tasks()
    
    def _create_celery_app(self) -> Celery:
        """创建Celery应用"""
        app = Celery('web_monitor')
        
        # 配置Celery
        app.conf.update(
            broker_url=config.celery.broker_url,
            result_backend=config.celery.result_backend,
            task_serializer=config.celery.task_serializer,
            accept_content=config.celery.accept_content,
            result_serializer=config.celery.result_serializer,
            timezone=config.celery.timezone,
            enable_utc=config.celery.enable_utc,
            task_routes=config.celery.task_routes,
            worker_prefetch_multiplier=1,
            task_acks_late=True,
            worker_disable_rate_limits=False,
            task_compression='gzip',
            result_compression='gzip',
            task_time_limit=300,  # 5分钟超时
            task_soft_time_limit=240,  # 4分钟软超时
            worker_max_tasks_per_child=1000,
            beat_schedule_filename='celerybeat-schedule',
        )
        
        logger.info("Celery应用创建成功")
        return app
    
    def _register_tasks(self):
        """注册任务"""
        
        @self.celery_app.task(bind=True, name='monitor.tasks.fetch_webpage')
        def fetch_webpage_task(self, website_id: int):
            """网页抓取任务"""
            task_id = str(uuid.uuid4())
            start_time = datetime.now(timezone.utc)
            
            # 记录任务开始
            db_manager.create_task_log({
                'task_id': task_id,
                'task_name': 'fetch_webpage',
                'website_id': website_id,
                'status': 'running',
                'start_time': start_time
            })
            
            try:
                from .fetcher import WebpageFetcher
                fetcher = WebpageFetcher()
                result = fetcher.fetch_website(website_id)
                
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                
                # 更新任务状态
                db_manager.update_task_log(task_id, {
                    'status': 'success',
                    'end_time': end_time,
                    'duration': duration,
                    'result_data': result
                })
                
                # 如果抓取成功，触发变化检测
                if result.get('success'):
                    self.celery_app.send_task(
                        'monitor.tasks.detect_changes',
                        args=[website_id, result['content_id']],
                        queue='detect'
                    )
                
                return result
                
            except Exception as e:
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                
                logger.error(f"网页抓取任务失败 - 网站ID: {website_id}, 错误: {str(e)}")
                
                # 更新任务状态
                db_manager.update_task_log(task_id, {
                    'status': 'failed',
                    'end_time': end_time,
                    'duration': duration,
                    'error_message': str(e)
                })
                
                raise
        
        @self.celery_app.task(bind=True, name='monitor.tasks.detect_changes')
        def detect_changes_task(self, website_id: int, new_content_id: int):
            """变化检测任务"""
            task_id = str(uuid.uuid4())
            start_time = datetime.now(timezone.utc)
            
            # 记录任务开始
            db_manager.create_task_log({
                'task_id': task_id,
                'task_name': 'detect_changes',
                'website_id': website_id,
                'status': 'running',
                'start_time': start_time
            })
            
            try:
                from .detector import ChangeDetector
                detector = ChangeDetector()
                result = detector.detect_changes(website_id, new_content_id)
                
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                
                # 更新任务状态
                db_manager.update_task_log(task_id, {
                    'status': 'success',
                    'end_time': end_time,
                    'duration': duration,
                    'result_data': result
                })
                
                # 如果检测到重要变化，发送通知
                if result.get('has_significant_change'):
                    self.celery_app.send_task(
                        'monitor.tasks.send_notification',
                        args=[website_id, result['change_id']],
                        queue='notify'
                    )
                
                return result
                
            except Exception as e:
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                
                logger.error(f"变化检测任务失败 - 网站ID: {website_id}, 错误: {str(e)}")
                
                # 更新任务状态
                db_manager.update_task_log(task_id, {
                    'status': 'failed',
                    'end_time': end_time,
                    'duration': duration,
                    'error_message': str(e)
                })
                
                raise
        
        @self.celery_app.task(bind=True, name='monitor.tasks.send_notification')
        def send_notification_task(self, website_id: int, change_id: int):
            """发送通知任务"""
            task_id = str(uuid.uuid4())
            start_time = datetime.now(timezone.utc)
            
            # 记录任务开始
            db_manager.create_task_log({
                'task_id': task_id,
                'task_name': 'send_notification',
                'website_id': website_id,
                'status': 'running',
                'start_time': start_time
            })
            
            try:
                from .notifier import NotificationManager
                notifier = NotificationManager()
                result = notifier.send_change_notification(website_id, change_id)
                
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                
                # 更新任务状态
                db_manager.update_task_log(task_id, {
                    'status': 'success',
                    'end_time': end_time,
                    'duration': duration,
                    'result_data': result
                })
                
                return result
                
            except Exception as e:
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                
                logger.error(f"通知发送任务失败 - 网站ID: {website_id}, 错误: {str(e)}")
                
                # 更新任务状态
                db_manager.update_task_log(task_id, {
                    'status': 'failed',
                    'end_time': end_time,
                    'duration': duration,
                    'error_message': str(e)
                })
                
                raise
        
        @self.celery_app.task(bind=True, name='monitor.tasks.system_monitor')
        def system_monitor_task(self):
            """系统监控任务"""
            try:
                # 收集系统指标
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                metrics_data = [
                    {
                        'metric_name': 'cpu_usage',
                        'metric_value': cpu_percent,
                        'metric_unit': 'percent',
                        'hostname': self.hostname
                    },
                    {
                        'metric_name': 'memory_usage',
                        'metric_value': memory.percent,
                        'metric_unit': 'percent',
                        'hostname': self.hostname
                    },
                    {
                        'metric_name': 'disk_usage',
                        'metric_value': disk.percent,
                        'metric_unit': 'percent',
                        'hostname': self.hostname
                    },
                    {
                        'metric_name': 'memory_available',
                        'metric_value': memory.available / (1024**3),  # GB
                        'metric_unit': 'GB',
                        'hostname': self.hostname
                    },
                    {
                        'metric_name': 'disk_free',
                        'metric_value': disk.free / (1024**3),  # GB
                        'metric_unit': 'GB',
                        'hostname': self.hostname
                    }
                ]
                
                # 保存指标
                db_manager.save_system_metrics(metrics_data)
                
                # 检查阈值告警
                self._check_system_alerts(cpu_percent, memory.percent, disk.percent)
                
                return {'status': 'success', 'metrics_count': len(metrics_data)}
                
            except Exception as e:
                logger.error(f"系统监控任务失败: {str(e)}")
                raise
        
        @self.celery_app.task(bind=True, name='monitor.tasks.cleanup_data')
        def cleanup_data_task(self):
            """数据清理任务"""
            try:
                db_manager.cleanup_old_data()
                return {'status': 'success'}
            except Exception as e:
                logger.error(f"数据清理任务失败: {str(e)}")
                raise
        
        logger.info("任务注册完成")
    
    def _setup_periodic_tasks(self):
        """设置定期任务"""
        
        # 系统监控任务 - 每分钟执行
        self.celery_app.conf.beat_schedule = {
            'system-monitor': {
                'task': 'monitor.tasks.system_monitor',
                'schedule': crontab(minute='*'),
            },
            'cleanup-data': {
                'task': 'monitor.tasks.cleanup_data',
                'schedule': crontab(hour=2, minute=0),  # 每天凌晨2点执行
            },
        }
        
        logger.info("定期任务设置完成")
    
    def _check_system_alerts(self, cpu_percent: float, memory_percent: float, disk_percent: float):
        """检查系统告警"""
        alerts = []
        
        if cpu_percent > config.monitoring.cpu_threshold:
            alerts.append(f"CPU使用率过高: {cpu_percent:.1f}%")
        
        if memory_percent > config.monitoring.memory_threshold:
            alerts.append(f"内存使用率过高: {memory_percent:.1f}%")
        
        if disk_percent > config.monitoring.disk_threshold:
            alerts.append(f"磁盘使用率过高: {disk_percent:.1f}%")
        
        if alerts:
            logger.warning(f"系统告警 - {self.hostname}: {'; '.join(alerts)}")
            # 这里可以发送系统告警通知
    
    def schedule_website_monitoring(self):
        """调度网站监控任务"""
        try:
            websites = db_manager.get_enabled_websites()
            scheduled_count = 0
            
            for website in websites:
                # 检查是否需要执行监控
                if self._should_monitor_website(website):
                    # 发送抓取任务
                    self.celery_app.send_task(
                        'monitor.tasks.fetch_webpage',
                        args=[website.id],
                        queue='fetch'
                    )
                    scheduled_count += 1
                    logger.debug(f"已调度网站监控任务 - ID: {website.id}, URL: {website.url}")
            
            logger.info(f"本轮调度完成，共调度 {scheduled_count} 个网站监控任务")
            return scheduled_count
            
        except Exception as e:
            logger.error(f"调度网站监控任务失败: {str(e)}")
            raise
    
    def _should_monitor_website(self, website: WebsiteModel) -> bool:
        """判断是否应该监控网站"""
        if not website.enabled:
            return False
        
        # 如果从未检查过，立即执行
        if not website.last_check_at:
            return True
        
        # 计算下次检查时间
        next_check_time = website.last_check_at + timedelta(minutes=website.interval_minutes)
        
        return datetime.now(timezone.utc) >= next_check_time
    
    def schedule_single_website(self, website_id: int) -> str:
        """调度单个网站的监控任务"""
        try:
            result = self.celery_app.send_task(
                'monitor.tasks.fetch_webpage',
                args=[website_id],
                queue='fetch'
            )
            
            logger.info(f"已调度单个网站监控任务 - 网站ID: {website_id}, 任务ID: {result.id}")
            return result.id
            
        except Exception as e:
            logger.error(f"调度单个网站监控任务失败 - 网站ID: {website_id}, 错误: {str(e)}")
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        try:
            result = self.celery_app.AsyncResult(task_id)
            
            return {
                'task_id': task_id,
                'status': result.status,
                'result': result.result if result.ready() else None,
                'traceback': result.traceback if result.failed() else None
            }
            
        except Exception as e:
            logger.error(f"获取任务状态失败 - 任务ID: {task_id}, 错误: {str(e)}")
            return {
                'task_id': task_id,
                'status': 'UNKNOWN',
                'error': str(e)
            }
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            self.celery_app.control.revoke(task_id, terminate=True)
            logger.info(f"任务已取消 - 任务ID: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"取消任务失败 - 任务ID: {task_id}, 错误: {str(e)}")
            return False
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        try:
            inspect = self.celery_app.control.inspect()
            
            # 获取活跃任务
            active_tasks = inspect.active()
            
            # 获取预定任务
            scheduled_tasks = inspect.scheduled()
            
            # 获取保留任务
            reserved_tasks = inspect.reserved()
            
            return {
                'active_tasks': active_tasks,
                'scheduled_tasks': scheduled_tasks,
                'reserved_tasks': reserved_tasks
            }
            
        except Exception as e:
            logger.error(f"获取队列状态失败: {str(e)}")
            return {'error': str(e)}
    
    def get_worker_status(self) -> Dict[str, Any]:
        """获取工作节点状态"""
        try:
            inspect = self.celery_app.control.inspect()
            
            # 获取工作节点统计信息
            stats = inspect.stats()
            
            # 获取注册的任务
            registered_tasks = inspect.registered()
            
            return {
                'stats': stats,
                'registered_tasks': registered_tasks
            }
            
        except Exception as e:
            logger.error(f"获取工作节点状态失败: {str(e)}")
            return {'error': str(e)}
            
    def start_worker(self, concurrency: int = 4, queues: list = None):
        """启动Celery工作进程"""
        if queues is None:
            queues = ['default']
            
        try:
            # 使用Celery的Worker API启动工作进程
            worker_args = [
                'worker',
                '--concurrency', str(concurrency),
                '--loglevel', 'INFO',
                '--queues', ','.join(queues)
            ]
            
            self.celery_app.worker_main(worker_args)
            
        except Exception as e:
            logger.error(f"启动工作进程失败: {str(e)}")
            raise
            
    def start_beat(self):
        """启动Celery定时任务调度器"""
        try:
            # 使用Celery的Beat API启动定时任务调度器
            beat_args = [
                'beat',
                '--loglevel', 'INFO'
            ]
            
            self.celery_app.beat_main(beat_args)
            
        except Exception as e:
            logger.error(f"启动定时任务调度器失败: {str(e)}")
            raise
    
    def start_scheduler(self):
        """启动调度器"""
        logger.info("任务调度器启动")
        
        # 这里可以添加定期调度逻辑
        # 例如每分钟检查一次需要监控的网站
        import schedule
        import time
        
        # 每分钟检查一次高优先级网站
        schedule.every(1).minutes.do(self._schedule_high_priority_websites)
        
        # 每5分钟检查一次中优先级网站
        schedule.every(5).minutes.do(self._schedule_medium_priority_websites)
        
        # 每30分钟检查一次低优先级网站
        schedule.every(30).minutes.do(self._schedule_low_priority_websites)
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    def _schedule_high_priority_websites(self):
        """调度高优先级网站"""
        self._schedule_websites_by_priority('high')
    
    def _schedule_medium_priority_websites(self):
        """调度中优先级网站"""
        self._schedule_websites_by_priority('medium')
    
    def _schedule_low_priority_websites(self):
        """调度低优先级网站"""
        self._schedule_websites_by_priority('low')
    
    def _schedule_websites_by_priority(self, priority: str):
        """按优先级调度网站"""
        try:
            with db_manager.get_session() as session:
                websites = session.query(WebsiteModel).filter(
                    WebsiteModel.enabled == True,
                    WebsiteModel.priority == priority
                ).all()
                
                scheduled_count = 0
                for website in websites:
                    if self._should_monitor_website(website):
                        self.celery_app.send_task(
                            'monitor.tasks.fetch_webpage',
                            args=[website.id],
                            queue='fetch'
                        )
                        scheduled_count += 1
                
                if scheduled_count > 0:
                    logger.info(f"调度了 {scheduled_count} 个{priority}优先级网站")
                    
        except Exception as e:
            logger.error(f"调度{priority}优先级网站失败: {str(e)}")


# 全局任务调度器实例
task_scheduler = TaskScheduler()