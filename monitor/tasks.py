# Celery任务定义

import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from celery import Celery, group, chord
from celery.exceptions import Retry
from loguru import logger
from .config import config
from .database import db_manager
from .fetcher import WebpageFetcher
from .detector import change_detector
from .notifier import notification_manager


# 创建Celery应用
celery_app = Celery(
    'monitor',
    broker=config.celery.broker_url,
    backend=config.celery.result_backend,
    include=['monitor.tasks']
)

# Celery配置
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_default_retry_delay=60,
    task_max_retries=3,
    task_routes={
        'monitor.tasks.fetch_website': {'queue': 'fetch'},
        'monitor.tasks.detect_changes': {'queue': 'detect'},
        'monitor.tasks.send_notification': {'queue': 'notify'},
        'monitor.tasks.cleanup_old_data': {'queue': 'maintenance'},
        'monitor.tasks.system_health_check': {'queue': 'system'},
    },
    beat_schedule={
        'schedule-website-monitoring': {
            'task': 'monitor.tasks.schedule_website_monitoring',
            'schedule': 300,  # 5分钟
        },
        'cleanup-old-data': {
            'task': 'monitor.tasks.cleanup_old_data',
            'schedule': 3600,  # 1小时
        },
        'system-health-check': {
            'task': 'monitor.tasks.system_health_check',
            'schedule': 600,  # 10分钟
        },
    }
)


@celery_app.task(bind=True, name='monitor.tasks.fetch_website')
def fetch_website(self, website_id: int) -> Dict[str, Any]:
    """抓取网站内容任务"""
    try:
        logger.info(f"开始抓取网站任务 - ID: {website_id}, Task: {self.request.id}")
        
        # 记录任务开始
        db_manager.log_task_start(self.request.id, 'fetch_website', {'website_id': website_id})
        
        # 执行抓取
        fetcher = WebpageFetcher()
        result = fetcher.fetch_website(website_id)
        
        # 记录任务完成
        db_manager.log_task_completion(
            self.request.id, 
            'fetch_website', 
            result['success'], 
            result.get('error')
        )
        
        if result['success']:
            logger.info(f"网站抓取任务完成 - ID: {website_id}, Content ID: {result.get('content_id')}")
            
            # 如果抓取成功，触发变化检测
            detect_changes.delay(website_id, result.get('content_id'))
        else:
            logger.warning(f"网站抓取任务失败 - ID: {website_id}, 错误: {result.get('error')}")
        
        return result
        
    except Exception as e:
        logger.error(f"网站抓取任务异常 - ID: {website_id}, 错误: {str(e)}")
        
        # 记录任务失败
        db_manager.log_task_completion(
            self.request.id, 
            'fetch_website', 
            False, 
            str(e)
        )
        
        # 重试机制
        if self.request.retries < self.max_retries:
            logger.info(f"重试网站抓取任务 - ID: {website_id}, 重试次数: {self.request.retries + 1}")
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=e)
        
        return {
            'success': False,
            'error': str(e),
            'website_id': website_id
        }


@celery_app.task(bind=True, name='monitor.tasks.detect_changes')
def detect_changes(self, website_id: int, content_id: Optional[int] = None) -> Dict[str, Any]:
    """检测网站变化任务"""
    try:
        logger.info(f"开始变化检测任务 - 网站ID: {website_id}, 内容ID: {content_id}, Task: {self.request.id}")
        
        # 记录任务开始
        db_manager.log_task_start(
            self.request.id, 
            'detect_changes', 
            {'website_id': website_id, 'content_id': content_id}
        )
        
        # 执行变化检测
        result = change_detector.detect_website_changes(website_id)
        
        if result is None:
            logger.info(f"变化检测跳过 - 网站ID: {website_id}")
            db_manager.log_task_completion(self.request.id, 'detect_changes', True, '检测跳过')
            return {'success': True, 'has_change': False, 'reason': '检测跳过'}
        
        # 记录任务完成
        db_manager.log_task_completion(
            self.request.id, 
            'detect_changes', 
            True, 
            None
        )
        
        if result.has_change:
            logger.info(f"检测到变化 - 网站ID: {website_id}, 变化分数: {result.change_score:.3f}")
            
            # 如果检测到变化，发送通知
            send_notification.delay(website_id, result.__dict__)
        else:
            logger.info(f"未检测到变化 - 网站ID: {website_id}")
        
        return {
            'success': True,
            'has_change': result.has_change,
            'change_score': result.change_score,
            'change_type': result.change_type,
            'website_id': website_id
        }
        
    except Exception as e:
        logger.error(f"变化检测任务异常 - 网站ID: {website_id}, 错误: {str(e)}")
        
        # 记录任务失败
        db_manager.log_task_completion(
            self.request.id, 
            'detect_changes', 
            False, 
            str(e)
        )
        
        return {
            'success': False,
            'error': str(e),
            'website_id': website_id
        }


@celery_app.task(bind=True, name='monitor.tasks.send_notification')
def send_notification(self, website_id: int, change_result_dict: Dict[str, Any]) -> Dict[str, Any]:
    """发送通知任务"""
    try:
        logger.info(f"开始发送通知任务 - 网站ID: {website_id}, Task: {self.request.id}")
        
        # 记录任务开始
        db_manager.log_task_start(
            self.request.id, 
            'send_notification', 
            {'website_id': website_id}
        )
        
        # 重构ChangeResult对象
        from .detector import ChangeResult
        change_result = ChangeResult(**change_result_dict)
        
        # 发送通知
        success = notification_manager.send_change_notification(website_id, change_result)
        
        # 记录任务完成
        db_manager.log_task_completion(
            self.request.id, 
            'send_notification', 
            success, 
            None if success else '通知发送失败'
        )
        
        if success:
            logger.info(f"通知发送成功 - 网站ID: {website_id}")
        else:
            logger.warning(f"通知发送失败 - 网站ID: {website_id}")
        
        return {
            'success': success,
            'website_id': website_id
        }
        
    except Exception as e:
        logger.error(f"发送通知任务异常 - 网站ID: {website_id}, 错误: {str(e)}")
        
        # 记录任务失败
        db_manager.log_task_completion(
            self.request.id, 
            'send_notification', 
            False, 
            str(e)
        )
        
        return {
            'success': False,
            'error': str(e),
            'website_id': website_id
        }


@celery_app.task(name='monitor.tasks.schedule_website_monitoring')
def schedule_website_monitoring() -> Dict[str, Any]:
    """调度网站监控任务"""
    try:
        logger.info("开始调度网站监控任务")
        
        # 获取需要监控的网站
        websites = db_manager.get_websites_for_monitoring()
        
        if not websites:
            logger.info("没有需要监控的网站")
            return {'success': True, 'scheduled_count': 0}
        
        # 按优先级和检查间隔分组
        high_priority_sites = []
        normal_priority_sites = []
        low_priority_sites = []
        
        current_time = datetime.now(timezone.utc)
        
        for website in websites:
            # 检查是否到了检查时间
            if website.last_check_at:
                time_since_check = current_time - website.last_check_at
                if time_since_check.total_seconds() < website.check_interval * 60:
                    continue
            
            # 根据优先级分组
            if website.priority == 'high':
                high_priority_sites.append(website.id)
            elif website.priority == 'low':
                low_priority_sites.append(website.id)
            else:
                normal_priority_sites.append(website.id)
        
        # 创建任务组
        scheduled_count = 0
        
        # 高优先级网站立即执行
        if high_priority_sites:
            high_priority_group = group(fetch_website.s(site_id) for site_id in high_priority_sites)
            high_priority_group.apply_async()
            scheduled_count += len(high_priority_sites)
            logger.info(f"调度高优先级网站监控任务: {len(high_priority_sites)} 个")
        
        # 普通优先级网站
        if normal_priority_sites:
            normal_priority_group = group(fetch_website.s(site_id) for site_id in normal_priority_sites)
            normal_priority_group.apply_async(countdown=30)  # 延迟30秒
            scheduled_count += len(normal_priority_sites)
            logger.info(f"调度普通优先级网站监控任务: {len(normal_priority_sites)} 个")
        
        # 低优先级网站
        if low_priority_sites:
            low_priority_group = group(fetch_website.s(site_id) for site_id in low_priority_sites)
            low_priority_group.apply_async(countdown=60)  # 延迟60秒
            scheduled_count += len(low_priority_sites)
            logger.info(f"调度低优先级网站监控任务: {len(low_priority_sites)} 个")
        
        logger.info(f"网站监控任务调度完成 - 总计: {scheduled_count} 个")
        
        return {
            'success': True,
            'scheduled_count': scheduled_count,
            'high_priority': len(high_priority_sites),
            'normal_priority': len(normal_priority_sites),
            'low_priority': len(low_priority_sites)
        }
        
    except Exception as e:
        logger.error(f"调度网站监控任务异常: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'scheduled_count': 0
        }


@celery_app.task(name='monitor.tasks.batch_fetch_websites')
def batch_fetch_websites(website_ids: List[int]) -> Dict[str, Any]:
    """批量抓取网站任务"""
    try:
        logger.info(f"开始批量抓取网站任务 - 数量: {len(website_ids)}")
        
        # 创建任务组
        job = group(fetch_website.s(website_id) for website_id in website_ids)
        result = job.apply_async()
        
        # 等待所有任务完成
        results = result.get(timeout=config.celery.task_time_limit)
        
        # 统计结果
        success_count = sum(1 for r in results if r.get('success', False))
        failed_count = len(results) - success_count
        
        logger.info(f"批量抓取网站任务完成 - 成功: {success_count}, 失败: {failed_count}")
        
        return {
            'success': True,
            'total_count': len(website_ids),
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"批量抓取网站任务异常: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'total_count': len(website_ids)
        }


@celery_app.task(name='monitor.tasks.cleanup_old_data')
def cleanup_old_data() -> Dict[str, Any]:
    """清理旧数据任务"""
    try:
        logger.info("开始清理旧数据任务")
        
        # 清理旧的网页内容
        content_retention_days = config.storage.content_retention_days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=content_retention_days)
        
        deleted_contents = db_manager.cleanup_old_contents(cutoff_date)
        logger.info(f"清理旧网页内容: {deleted_contents} 条")
        
        # 清理旧的变化检测记录
        detection_retention_days = config.storage.detection_retention_days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=detection_retention_days)
        
        deleted_detections = db_manager.cleanup_old_detections(cutoff_date)
        logger.info(f"清理旧变化检测记录: {deleted_detections} 条")
        
        # 清理旧的任务日志
        log_retention_days = config.storage.log_retention_days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=log_retention_days)
        
        deleted_logs = db_manager.cleanup_old_task_logs(cutoff_date)
        logger.info(f"清理旧任务日志: {deleted_logs} 条")
        
        # 清理Redis缓存
        cache_cleaned = db_manager.cleanup_expired_cache()
        logger.info(f"清理过期缓存: {cache_cleaned} 个键")
        
        total_cleaned = deleted_contents + deleted_detections + deleted_logs + cache_cleaned
        
        logger.info(f"数据清理任务完成 - 总计清理: {total_cleaned} 条记录")
        
        return {
            'success': True,
            'deleted_contents': deleted_contents,
            'deleted_detections': deleted_detections,
            'deleted_logs': deleted_logs,
            'cache_cleaned': cache_cleaned,
            'total_cleaned': total_cleaned
        }
        
    except Exception as e:
        logger.error(f"清理旧数据任务异常: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@celery_app.task(name='monitor.tasks.system_health_check')
def system_health_check() -> Dict[str, Any]:
    """系统健康检查任务"""
    try:
        logger.info("开始系统健康检查任务")
        
        health_status = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'database': False,
            'redis': False,
            'celery_workers': 0,
            'active_websites': 0,
            'recent_errors': 0,
            'disk_usage': 0.0,
            'memory_usage': 0.0
        }
        
        # 检查数据库连接
        try:
            db_manager.test_connection()
            health_status['database'] = True
        except Exception as e:
            logger.error(f"数据库连接检查失败: {str(e)}")
        
        # 检查Redis连接
        try:
            db_manager.test_redis_connection()
            health_status['redis'] = True
        except Exception as e:
            logger.error(f"Redis连接检查失败: {str(e)}")
        
        # 检查Celery工作进程
        try:
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            health_status['celery_workers'] = len(stats) if stats else 0
        except Exception as e:
            logger.error(f"Celery工作进程检查失败: {str(e)}")
        
        # 检查活跃网站数量
        try:
            health_status['active_websites'] = db_manager.get_active_websites_count()
        except Exception as e:
            logger.error(f"活跃网站数量检查失败: {str(e)}")
        
        # 检查最近错误数量
        try:
            health_status['recent_errors'] = db_manager.get_recent_errors_count(hours=24)
        except Exception as e:
            logger.error(f"最近错误数量检查失败: {str(e)}")
        
        # 检查系统资源使用情况
        try:
            import psutil
            health_status['disk_usage'] = psutil.disk_usage('/').percent
            health_status['memory_usage'] = psutil.virtual_memory().percent
        except Exception as e:
            logger.warning(f"系统资源检查失败: {str(e)}")
        
        # 保存健康检查结果
        db_manager.save_system_metrics(health_status)
        
        # 检查是否需要发送警报
        alerts = []
        
        if not health_status['database']:
            alerts.append('数据库连接失败')
        
        if not health_status['redis']:
            alerts.append('Redis连接失败')
        
        if health_status['celery_workers'] == 0:
            alerts.append('没有可用的Celery工作进程')
        
        if health_status['disk_usage'] > 90:
            alerts.append(f'磁盘使用率过高: {health_status["disk_usage"]:.1f}%')
        
        if health_status['memory_usage'] > 90:
            alerts.append(f'内存使用率过高: {health_status["memory_usage"]:.1f}%')
        
        if health_status['recent_errors'] > 100:
            alerts.append(f'最近24小时错误数量过多: {health_status["recent_errors"]}')
        
        # 发送系统警报
        if alerts:
            alert_content = '\n'.join(alerts)
            notification_manager.send_system_notification(
                '🚨 系统健康检查警报',
                f'检测到以下问题:\n{alert_content}',
                'urgent'
            )
            logger.warning(f"系统健康检查发现问题: {alert_content}")
        
        logger.info("系统健康检查任务完成")
        
        return {
            'success': True,
            'health_status': health_status,
            'alerts': alerts
        }
        
    except Exception as e:
        logger.error(f"系统健康检查任务异常: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@celery_app.task(name='monitor.tasks.manual_check_website')
def manual_check_website(website_id: int) -> Dict[str, Any]:
    """手动检查网站任务"""
    try:
        logger.info(f"开始手动检查网站任务 - ID: {website_id}")
        
        # 创建任务链：抓取 -> 检测 -> 通知
        from celery import chain
        
        workflow = chain(
            fetch_website.s(website_id),
            detect_changes.s(website_id)
        )
        
        result = workflow.apply_async()
        
        logger.info(f"手动检查网站任务已提交 - ID: {website_id}, Task Chain: {result.id}")
        
        return {
            'success': True,
            'website_id': website_id,
            'task_id': result.id
        }
        
    except Exception as e:
        logger.error(f"手动检查网站任务异常 - ID: {website_id}, 错误: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'website_id': website_id
        }


# 任务状态查询函数
def get_task_status(task_id: str) -> Dict[str, Any]:
    """获取任务状态"""
    try:
        result = celery_app.AsyncResult(task_id)
        
        return {
            'task_id': task_id,
            'status': result.status,
            'result': result.result,
            'traceback': result.traceback,
            'date_done': result.date_done.isoformat() if result.date_done else None
        }
        
    except Exception as e:
        return {
            'task_id': task_id,
            'status': 'ERROR',
            'error': str(e)
        }


# 队列状态缓存
_queue_status_cache = {
    'data': None,
    'last_update': 0,
    'cache_ttl': 10  # 缓存有效期（秒）
}

# 队列状态查询函数
def get_queue_status() -> Dict[str, Any]:
    """获取队列状态（带缓存机制）"""
    global _queue_status_cache
    
    current_time = time.time()
    
    # 如果缓存有效，直接返回缓存数据
    if (_queue_status_cache['data'] is not None and 
        current_time - _queue_status_cache['last_update'] < _queue_status_cache['cache_ttl']):
        return _queue_status_cache['data']
    
    try:
        inspect = celery_app.control.inspect()
        
        # 获取活跃任务
        active_tasks = inspect.active()
        
        # 获取预定任务
        scheduled_tasks = inspect.scheduled()
        
        # 获取保留任务
        reserved_tasks = inspect.reserved()
        
        # 获取统计信息
        stats = inspect.stats()
        
        result = {
            'active_tasks': active_tasks,
            'scheduled_tasks': scheduled_tasks,
            'reserved_tasks': reserved_tasks,
            'worker_stats': stats
        }
        
        # 更新缓存
        _queue_status_cache['data'] = result
        _queue_status_cache['last_update'] = current_time
        
        return result
        
    except Exception as e:
        logger.error(f"获取队列状态失败: {str(e)}")
        return {
            'error': str(e)
        }