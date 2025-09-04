# 数据库管理模块

import redis
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float, JSON, Index, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from loguru import logger
from .config import get_config

# 数据库基类
Base = declarative_base()


class WebsiteModel(Base):
    """网站监控配置表"""
    __tablename__ = 'websites'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment='网站名称')
    url = Column(Text, nullable=False, comment='监控URL')
    selector = Column(Text, comment='CSS选择器，用于提取特定内容')
    xpath = Column(Text, comment='XPath选择器')
    monitor_type = Column(String(50), default='content', comment='监控类型：content/structure/image')
    priority = Column(String(20), default='medium', comment='优先级：high/medium/low')
    interval_minutes = Column(Integer, default=30, comment='检查间隔（分钟）')
    enabled = Column(Boolean, default=True, comment='是否启用')
    use_selenium = Column(Boolean, default=False, comment='是否使用Selenium')
    headers = Column(JSON, comment='自定义请求头')
    cookies = Column(JSON, comment='自定义Cookie')
    proxy = Column(String(255), comment='代理地址')
    user_agent = Column(String(500), comment='自定义User-Agent')
    ignore_html_tags = Column(Boolean, default=False, comment='是否忽略HTML标签')
    ignore_whitespace = Column(Boolean, default=True, comment='是否忽略空白字符')
    ignore_patterns = Column(JSON, comment='忽略的正则表达式模式列表')
    ignore_timestamps = Column(Boolean, default=True, comment='是否忽略时间戳变化')
    ignore_numbers = Column(Boolean, default=False, comment='是否忽略数字变化')
    notification_emails = Column(JSON, comment='通知邮箱列表')
    webhook_urls = Column(JSON, comment='Webhook通知URL列表')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment='创建时间')
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')
    last_check_at = Column(DateTime, comment='最后检查时间')
    last_change_at = Column(DateTime, comment='最后变化时间')
    check_count = Column(Integer, default=0, comment='检查次数')
    change_count = Column(Integer, default=0, comment='变化次数')
    last_status_code = Column(Integer, comment='最后状态码')
    last_error = Column(Text, comment='最后错误信息')
    consecutive_errors = Column(Integer, default=0, comment='连续错误次数')
    
    # 索引
    __table_args__ = (
        Index('idx_websites_url', 'url'),
        Index('idx_websites_enabled', 'enabled'),
        Index('idx_websites_priority', 'priority'),
        Index('idx_websites_last_check', 'last_check_at'),
    )


class WebpageContentModel(Base):
    """网页内容存储表"""
    __tablename__ = 'webpage_contents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    website_id = Column(Integer, nullable=False, comment='网站ID')
    content_hash = Column(String(64), nullable=False, comment='内容哈希值')
    raw_content = Column(Text, comment='原始HTML内容')
    extracted_content = Column(Text, comment='提取的目标内容')
    content_length = Column(Integer, comment='内容长度')
    response_time = Column(Float, comment='响应时间（秒）')
    status_code = Column(Integer, comment='HTTP状态码')
    error_message = Column(Text, comment='错误信息')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment='创建时间')
    
    # 索引
    __table_args__ = (
        Index('idx_webpage_contents_website_id', 'website_id'),
        Index('idx_webpage_contents_hash', 'content_hash'),
        Index('idx_webpage_contents_created_at', 'created_at'),
    )


class ChangeDetectionModel(Base):
    """变化检测记录表"""
    __tablename__ = 'change_detections'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    website_id = Column(Integer, nullable=False, comment='网站ID')
    old_content_id = Column(Integer, comment='旧内容ID')
    new_content_id = Column(Integer, comment='新内容ID')
    change_type = Column(String(50), comment='变化类型：content/structure/image')
    similarity_score = Column(Float, comment='相似度分数')
    change_summary = Column(Text, comment='变化摘要')
    change_details = Column(JSON, comment='详细变化信息')
    is_significant = Column(Boolean, default=True, comment='是否为重要变化')
    notification_sent = Column(Boolean, default=False, comment='是否已发送通知')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment='创建时间')
    
    # 索引
    __table_args__ = (
        Index('idx_change_detections_website_id', 'website_id'),
        Index('idx_change_detections_created_at', 'created_at'),
        Index('idx_change_detections_significant', 'is_significant'),
        Index('idx_change_detections_notification', 'notification_sent'),
    )


class TaskLogModel(Base):
    """任务执行日志表"""
    __tablename__ = 'task_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(255), nullable=False, comment='任务ID')
    task_name = Column(String(255), nullable=False, comment='任务名称')
    website_id = Column(Integer, comment='网站ID')
    status = Column(String(50), nullable=False, comment='任务状态：pending/running/success/failed')
    start_time = Column(DateTime, comment='开始时间')
    end_time = Column(DateTime, comment='结束时间')
    duration = Column(Float, comment='执行时长（秒）')
    error_message = Column(Text, comment='错误信息')
    result_data = Column(JSON, comment='执行结果数据')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment='创建时间')
    
    # 索引
    __table_args__ = (
        Index('idx_task_logs_task_id', 'task_id'),
        Index('idx_task_logs_website_id', 'website_id'),
        Index('idx_task_logs_status', 'status'),
        Index('idx_task_logs_created_at', 'created_at'),
    )


class SystemMetricsModel(Base):
    """系统监控指标表"""
    __tablename__ = 'system_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), nullable=False, comment='指标名称')
    metric_value = Column(Float, nullable=False, comment='指标值')
    metric_unit = Column(String(20), comment='指标单位')
    hostname = Column(String(255), comment='主机名')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment='创建时间')
    
    # 索引
    __table_args__ = (
        Index('idx_system_metrics_name', 'metric_name'),
        Index('idx_system_metrics_created_at', 'created_at'),
        Index('idx_system_metrics_hostname', 'hostname'),
    )


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, database_url=None, skip_db_check=False):
        self.engine = None
        self.session_factory = None
        self.redis_client = None
        
        # 如果跳过数据库检查，则不初始化数据库连接
        if not skip_db_check:
            self._initialize_database(database_url)
            self._initialize_redis()
        else:
            logger.warning("跳过数据库初始化，数据库功能将不可用")
            # 设置一个空的session_factory，避免调用get_session时出错
            self.session_factory = lambda: None
    
    def _initialize_database(self, database_url=None):
        """初始化数据库连接"""
        try:
            # 如果提供了自定义数据库URL，使用它
            if database_url:
                db_url = database_url
                logger.info(f"使用自定义数据库URL: {database_url}")
            else:
                # 检查环境变量中是否有数据库URL
                import os
                env_db_url = os.environ.get('DATABASE_URL')
                if env_db_url:
                    db_url = env_db_url
                    logger.info(f"使用环境变量中的数据库URL: {db_url}")
                else:
                    # 尝试使用PostgreSQL
                    try:
                        import psycopg2
                        config = get_config()
                        db_url = config.get_database_url()
                        logger.info("使用PostgreSQL数据库")
                    except ImportError:
                        # 如果没有psycopg2，使用SQLite
                        db_url = "sqlite:///monitor.db"
                        logger.warning("psycopg2未安装，使用SQLite数据库")
            
            # 根据数据库类型设置不同的参数
            if db_url.startswith('sqlite'):
                self.engine = create_engine(
                    db_url,
                    echo=False,
                    connect_args={'check_same_thread': False}
                )
            else:
                config = get_config()
                self.engine = create_engine(
                    db_url,
                    poolclass=QueuePool,
                    pool_size=config.database.postgresql_pool_size,
                    max_overflow=config.database.postgresql_max_overflow,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    echo=False
                )
            
            self.session_factory = sessionmaker(bind=self.engine)
            
            # 创建所有表
            Base.metadata.create_all(self.engine)
            
            logger.info("数据库连接初始化成功")
            
        except Exception as e:
            logger.error(f"数据库连接初始化失败: {e}")
            raise
    
    def _initialize_redis(self):
        """初始化Redis连接"""
        try:
            # 检查环境变量中是否有Redis URL
            import os
            from urllib.parse import urlparse
            
            redis_url = os.environ.get('REDIS_URL')
            if redis_url:
                # 解析Redis URL
                parsed_url = urlparse(redis_url)
                host = parsed_url.hostname or 'localhost'
                port = parsed_url.port or 6379
                db = int(parsed_url.path.lstrip('/') or 0)
                password = parsed_url.password
                
                logger.info(f"使用环境变量中的Redis URL: {redis_url}")
            else:
                # 使用配置文件中的设置
                config = get_config()
                host = config.database.redis_host
                port = config.database.redis_port
                db = config.database.redis_db
                password = config.database.redis_password
                
                logger.info(f"使用配置文件中的Redis设置: {host}:{port}")
            
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                max_connections=config.database.redis_max_connections,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # 测试连接
            self.redis_client.ping()
            
            logger.info("Redis连接初始化成功")
            
        except Exception as e:
            logger.error(f"Redis连接初始化失败: {e}")
            # 在Redis连接失败时，不要抛出异常，而是设置为None
            self.redis_client = None
            logger.warning("Redis连接失败，某些功能可能不可用")
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.session_factory()
    
    def get_redis(self) -> Optional[redis.Redis]:
        """获取Redis客户端"""
        return self.redis_client
        
    def is_redis_available(self) -> bool:
        """检查Redis是否可用"""
        return self.redis_client is not None
    
    def create_tables(self):
        """创建数据库表"""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("数据库表创建成功")
        except Exception as e:
            logger.error(f"数据库表创建失败: {e}")
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
        if self.redis_client:
            self.redis_client.close()
        logger.info("数据库连接已关闭")
    
    # 网站管理方法
    def create_website(self, website_data: Dict[str, Any]) -> int:
        """创建网站监控配置"""
        with self.get_session() as session:
            website = WebsiteModel(**website_data)
            session.add(website)
            session.commit()
            session.refresh(website)
            return website.id
    
    def get_website(self, website_id: int) -> Optional[WebsiteModel]:
        """获取网站配置"""
        with self.get_session() as session:
            return session.query(WebsiteModel).filter(WebsiteModel.id == website_id).first()
    
    def get_enabled_websites(self) -> List[WebsiteModel]:
        """获取所有启用的网站"""
        with self.get_session() as session:
            return session.query(WebsiteModel).filter(WebsiteModel.enabled == True).all()
    
    def update_website_check_time(self, website_id: int):
        """更新网站最后检查时间"""
        with self.get_session() as session:
            website = session.query(WebsiteModel).filter(WebsiteModel.id == website_id).first()
            if website:
                website.last_check_at = datetime.now(timezone.utc)
                website.check_count += 1
                session.commit()
    
    def update_website_change_time(self, website_id: int):
        """更新网站最后变化时间"""
        with self.get_session() as session:
            website = session.query(WebsiteModel).filter(WebsiteModel.id == website_id).first()
            if website:
                website.last_change_at = datetime.now(timezone.utc)
                website.change_count += 1
                session.commit()
    
    # 内容管理方法
    def save_webpage_content(self, content_data: Dict[str, Any]) -> int:
        """保存网页内容"""
        with self.get_session() as session:
            content = WebpageContentModel(**content_data)
            session.add(content)
            session.commit()
            session.refresh(content)
            return content.id
    
    def get_latest_content(self, website_id: int) -> Optional[WebpageContentModel]:
        """获取最新的网页内容"""
        with self.get_session() as session:
            return session.query(WebpageContentModel).filter(
                WebpageContentModel.website_id == website_id
            ).order_by(WebpageContentModel.created_at.desc()).first()
    
    # 变化检测方法
    def save_change_detection(self, change_data: Dict[str, Any]) -> int:
        """保存变化检测结果"""
        with self.get_session() as session:
            change = ChangeDetectionModel(**change_data)
            session.add(change)
            session.commit()
            session.refresh(change)
            return change.id
    
    def get_recent_changes(self, website_id: Optional[int] = None, limit: int = 10) -> List[ChangeDetectionModel]:
        """获取最近的变化记录
        
        Args:
            website_id: 可选的网站ID，如果提供则只返回该网站的变化
            limit: 返回记录的最大数量
        """
        with self.get_session() as session:
            query = session.query(ChangeDetectionModel)
            if website_id is not None:
                query = query.filter(ChangeDetectionModel.website_id == website_id)
            return query.order_by(ChangeDetectionModel.created_at.desc()).limit(limit).all()
    
    # 任务日志方法
    def create_task_log(self, log_data: Dict[str, Any]) -> int:
        """创建任务日志"""
        with self.get_session() as session:
            task_log = TaskLogModel(**log_data)
            session.add(task_log)
            session.commit()
            session.refresh(task_log)
            return task_log.id
    
    def update_task_log(self, task_id: str, update_data: Dict[str, Any]):
        """更新任务日志"""
        with self.get_session() as session:
            task_log = session.query(TaskLogModel).filter(TaskLogModel.task_id == task_id).first()
            if task_log:
                for key, value in update_data.items():
                    setattr(task_log, key, value)
                session.commit()
    
    # 系统监控方法
    def save_system_metrics(self, metrics_data: List[Dict[str, Any]]):
        """保存系统监控指标"""
        with self.get_session() as session:
            metrics = [SystemMetricsModel(**data) for data in metrics_data]
            session.add_all(metrics)
            session.commit()
    
    # 缓存方法
    def set_cache(self, key: str, value: str, ttl: int = 3600):
        """设置缓存"""
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, value)
            except Exception as e:
                logger.error(f"设置缓存失败: {e}")
    
    def get_cache(self, key: str) -> Optional[str]:
        """获取缓存"""
        if self.redis_client:
            try:
                return self.redis_client.get(key)
            except Exception as e:
                logger.error(f"获取缓存失败: {e}")
        return None
    
    def delete_cache(self, key: str):
        """删除缓存"""
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception as e:
                logger.error(f"删除缓存失败: {e}")
    
    def clear_cache_pattern(self, pattern: str):
        """清除匹配模式的缓存"""
        if self.redis_client:
            try:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception as e:
                logger.error(f"清除缓存模式失败: {e}")
    
    def get_daily_statistics(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取每日统计数据
        
        Args:
            days: 返回的天数
            
        Returns:
            包含每日统计数据的列表
        """
        result = []
        with self.get_session() as session:
            # 计算日期范围
            end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = end_date - timedelta(days=days)
            
            # 生成日期列表
            date_list = [start_date + timedelta(days=i) for i in range(days + 1)]
            
            for i in range(len(date_list) - 1):
                current_date = date_list[i]
                next_date = date_list[i + 1]
                
                # 获取当天的检查次数
                checks_count = session.query(func.count(WebpageContentModel.id)).filter(
                    WebpageContentModel.created_at >= current_date,
                    WebpageContentModel.created_at < next_date
                ).scalar()
                
                # 获取当天的变化次数
                changes_count = session.query(func.count(ChangeDetectionModel.id)).filter(
                    ChangeDetectionModel.created_at >= current_date,
                    ChangeDetectionModel.created_at < next_date
                ).scalar()
                
                # 添加到结果列表
                result.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'checks': checks_count,
                    'changes': changes_count
                })
        
        return result
    
    # 数据清理方法
    def cleanup_old_data(self):
        """清理过期数据"""
        config = get_config()
        with self.get_session() as session:
            # 清理过期的原始内容
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=config.storage.raw_data_retention_days)
            session.query(WebpageContentModel).filter(
                WebpageContentModel.created_at < cutoff_date
            ).delete()
            
            # 清理过期的变化历史
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=config.storage.change_history_retention_days)
            session.query(ChangeDetectionModel).filter(
                ChangeDetectionModel.created_at < cutoff_date
            ).delete()
            
            # 清理过期的任务日志
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=config.storage.logs_retention_days)
            session.query(TaskLogModel).filter(
                TaskLogModel.created_at < cutoff_date
            ).delete()
            
            # 清理过期的系统指标
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=config.storage.logs_retention_days)
            session.query(SystemMetricsModel).filter(
                SystemMetricsModel.created_at < cutoff_date
            ).delete()
            
            session.commit()
            logger.info("过期数据清理完成")
    
    # 统计方法
    def get_total_websites_count(self) -> int:
        """获取网站总数"""
        with self.get_session() as session:
            return session.query(WebsiteModel).count()
    
    def get_active_websites_count(self) -> int:
        """获取活跃网站数量"""
        with self.get_session() as session:
            return session.query(WebsiteModel).filter(WebsiteModel.enabled == True).count()
    
    def get_total_checks_count(self) -> int:
        """获取总检查次数"""
        with self.get_session() as session:
            result = session.query(WebsiteModel).with_entities(
                func.sum(WebsiteModel.check_count)
            ).scalar()
            return result or 0
    
    def get_recent_changes_count(self, hours: int = 24) -> int:
        """获取最近变化数量"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        with self.get_session() as session:
            return session.query(ChangeDetectionModel).filter(
                ChangeDetectionModel.created_at >= cutoff_time
            ).count()
    
    def get_websites_paginated(self, page: int = 1, per_page: int = 20) -> List[WebsiteModel]:
        """获取分页的网站列表"""
        with self.get_session() as session:
            offset = (page - 1) * per_page
            return session.query(WebsiteModel).order_by(WebsiteModel.id.desc()).offset(offset).limit(per_page).all()
    
    def search_websites(self, search_term: str = '', page: int = 1, per_page: int = 20) -> List[WebsiteModel]:
        """搜索网站"""
        with self.get_session() as session:
            offset = (page - 1) * per_page
            query = session.query(WebsiteModel)
            
            if search_term:
                query = query.filter(
                    WebsiteModel.name.ilike(f'%{search_term}%') | 
                    WebsiteModel.url.ilike(f'%{search_term}%')
                )
                
            return query.order_by(WebsiteModel.id.desc()).offset(offset).limit(per_page).all()
    
    def get_latest_contents(self, website_id: int, limit: int = 10) -> List[WebpageContentModel]:
        """获取最新的网页内容列表"""
        with self.get_session() as session:
            return session.query(WebpageContentModel).filter(
                WebpageContentModel.website_id == website_id
            ).order_by(WebpageContentModel.created_at.desc()).limit(limit).all()
    
    def get_change_history(self, website_id: int, limit: int = 20) -> List[ChangeDetectionModel]:
        """获取变化历史"""
        with self.get_session() as session:
            return session.query(ChangeDetectionModel).filter(
                ChangeDetectionModel.website_id == website_id
            ).order_by(ChangeDetectionModel.created_at.desc()).limit(limit).all()
    
    def get_website_statistics(self, website_id: int) -> Dict[str, Any]:
        """获取网站统计信息"""
        with self.get_session() as session:
            website = session.query(WebsiteModel).filter(WebsiteModel.id == website_id).first()
            if not website:
                return {}
                
            # 获取最近24小时的变化数量
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            recent_changes = session.query(ChangeDetectionModel).filter(
                ChangeDetectionModel.website_id == website_id,
                ChangeDetectionModel.created_at >= cutoff_time
            ).count()
            
            return {
                'check_count': website.check_count,
                'change_count': website.change_count,
                'recent_changes': recent_changes,
                'last_check': website.last_check_at,
                'last_change': website.last_change_at
            }
    
    def get_recent_task_logs(self, limit: int = 50) -> List[TaskLogModel]:
        """获取最近的任务日志"""
        with self.get_session() as session:
            return session.query(TaskLogModel).order_by(TaskLogModel.created_at.desc()).limit(limit).all()
    
    def get_latest_system_metrics(self) -> Dict[str, Any]:
        """获取最新的系统指标"""
        with self.get_session() as session:
            metrics = session.query(SystemMetricsModel).order_by(SystemMetricsModel.created_at.desc()).first()
            if not metrics:
                return {}
                
            return {
                'cpu_percent': metrics.cpu_percent,
                'memory_percent': metrics.memory_percent,
                'disk_percent': metrics.disk_percent,
                'created_at': metrics.created_at
            }


# 全局数据库管理器实例
import os
skip_db_check = os.environ.get('SKIP_DB_CHECK', '').lower() == 'true'

if skip_db_check:
    logger.info("检测到SKIP_DB_CHECK环境变量，跳过数据库管理器初始化")
    db_manager = None
else:
    db_manager = DatabaseManager()