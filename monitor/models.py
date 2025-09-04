#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模型定义
定义网页监控系统的所有数据模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Website(Base):
    """网站监控配置表"""
    __tablename__ = 'websites'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment='网站名称')
    url = Column(Text, nullable=False, comment='监控URL')
    description = Column(Text, comment='网站描述')
    
    # 监控配置
    check_interval = Column(Integer, default=300, comment='检查间隔(秒)')
    detection_algorithm = Column(String(50), default='hash', comment='检测算法')
    fetcher_type = Column(String(50), default='requests', comment='抓取器类型')
    
    # 选择器配置
    css_selector = Column(Text, comment='CSS选择器')
    xpath_selector = Column(Text, comment='XPath选择器')
    exclude_selectors = Column(JSON, comment='排除选择器列表')
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment='是否启用')
    last_check_time = Column(DateTime, comment='最后检查时间')
    last_change_time = Column(DateTime, comment='最后变化时间')
    check_count = Column(Integer, default=0, comment='检查次数')
    change_count = Column(Integer, default=0, comment='变化次数')
    
    # 状态码和错误信息
    last_status_code = Column(Integer, comment='最后状态码')
    last_error = Column(Text, comment='最后错误信息')
    consecutive_errors = Column(Integer, default=0, comment='连续错误次数')
    
    # 通知配置
    notification_enabled = Column(Boolean, default=True, comment='是否启用通知')
    notification_methods = Column(JSON, comment='通知方式配置')
    notification_threshold = Column(Integer, default=1, comment='通知阈值')
    
    # 高级配置
    headers = Column(JSON, comment='自定义请求头')
    cookies = Column(JSON, comment='自定义Cookie')
    proxy_config = Column(JSON, comment='代理配置')
    timeout = Column(Integer, default=30, comment='超时时间(秒)')
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关联关系
    contents = relationship('WebpageContent', back_populates='website', cascade='all, delete-orphan')
    change_records = relationship('ChangeRecord', back_populates='website', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Website(id={self.id}, name="{self.name}", url="{self.url}")>'


class WebpageContent(Base):
    """网页内容存储表"""
    __tablename__ = 'webpage_contents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    website_id = Column(Integer, ForeignKey('websites.id'), nullable=False, comment='网站ID')
    
    # 内容信息
    content_hash = Column(String(64), nullable=False, comment='内容哈希值')
    content_text = Column(Text, comment='文本内容')
    content_html = Column(Text, comment='HTML内容')
    content_size = Column(Integer, comment='内容大小(字节)')
    
    # 页面信息
    title = Column(String(500), comment='页面标题')
    status_code = Column(Integer, comment='HTTP状态码')
    response_time = Column(Float, comment='响应时间(秒)')
    
    # 元数据
    headers = Column(JSON, comment='响应头信息')
    cookies = Column(JSON, comment='Cookie信息')
    
    # 截图信息(如果使用Selenium)
    screenshot_path = Column(String(500), comment='截图文件路径')
    screenshot_hash = Column(String(64), comment='截图哈希值')
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    
    # 关联关系
    website = relationship('Website', back_populates='contents')
    
    def __repr__(self):
        return f'<WebpageContent(id={self.id}, website_id={self.website_id}, hash="{self.content_hash[:8]}...")>'


class ChangeRecord(Base):
    """变化记录表"""
    __tablename__ = 'change_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    website_id = Column(Integer, ForeignKey('websites.id'), nullable=False, comment='网站ID')
    
    # 变化信息
    change_type = Column(String(50), nullable=False, comment='变化类型')
    old_content_id = Column(Integer, ForeignKey('webpage_contents.id'), comment='旧内容ID')
    new_content_id = Column(Integer, ForeignKey('webpage_contents.id'), comment='新内容ID')
    
    # 变化详情
    change_summary = Column(Text, comment='变化摘要')
    change_details = Column(JSON, comment='变化详情')
    similarity_score = Column(Float, comment='相似度分数')
    
    # 差异信息
    diff_text = Column(Text, comment='文本差异')
    diff_html = Column(Text, comment='HTML差异')
    
    # 通知状态
    notification_sent = Column(Boolean, default=False, comment='是否已发送通知')
    notification_methods = Column(JSON, comment='已发送的通知方式')
    notification_time = Column(DateTime, comment='通知发送时间')
    
    # 时间戳
    detected_at = Column(DateTime, default=func.now(), comment='检测时间')
    
    # 关联关系
    website = relationship('Website', back_populates='change_records')
    old_content = relationship('WebpageContent', foreign_keys=[old_content_id])
    new_content = relationship('WebpageContent', foreign_keys=[new_content_id])
    
    def __repr__(self):
        return f'<ChangeRecord(id={self.id}, website_id={self.website_id}, type="{self.change_type}")>'


class TaskRecord(Base):
    """任务执行记录表"""
    __tablename__ = 'task_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(255), nullable=False, comment='任务ID')
    task_name = Column(String(255), nullable=False, comment='任务名称')
    website_id = Column(Integer, ForeignKey('websites.id'), comment='关联网站ID')
    
    # 任务状态
    status = Column(String(50), nullable=False, comment='任务状态')
    progress = Column(Integer, default=0, comment='任务进度(0-100)')
    
    # 执行信息
    started_at = Column(DateTime, comment='开始时间')
    finished_at = Column(DateTime, comment='结束时间')
    duration = Column(Float, comment='执行时长(秒)')
    
    # 结果信息
    result = Column(JSON, comment='任务结果')
    error_message = Column(Text, comment='错误信息')
    traceback = Column(Text, comment='错误堆栈')
    
    # 资源使用
    cpu_usage = Column(Float, comment='CPU使用率')
    memory_usage = Column(Float, comment='内存使用量(MB)')
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    def __repr__(self):
        return f'<TaskRecord(id={self.id}, task_id="{self.task_id}", status="{self.status}")>'


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = 'system_configs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), nullable=False, unique=True, comment='配置键')
    value = Column(Text, comment='配置值')
    description = Column(Text, comment='配置描述')
    category = Column(String(100), comment='配置分类')
    
    # 配置属性
    is_encrypted = Column(Boolean, default=False, comment='是否加密存储')
    is_readonly = Column(Boolean, default=False, comment='是否只读')
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    def __repr__(self):
        return f'<SystemConfig(key="{self.key}", category="{self.category}")>'


class UserSession(Base):
    """用户会话表"""
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, unique=True, comment='会话ID')
    user_id = Column(String(255), comment='用户ID')
    
    # 会话信息
    ip_address = Column(String(45), comment='IP地址')
    user_agent = Column(Text, comment='用户代理')
    
    # 时间信息
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    last_activity = Column(DateTime, default=func.now(), comment='最后活动时间')
    expires_at = Column(DateTime, comment='过期时间')
    
    # 状态
    is_active = Column(Boolean, default=True, comment='是否活跃')
    
    def __repr__(self):
        return f'<UserSession(session_id="{self.session_id}", user_id="{self.user_id}")>'


class NotificationLog(Base):
    """通知日志表"""
    __tablename__ = 'notification_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    website_id = Column(Integer, ForeignKey('websites.id'), comment='网站ID')
    change_record_id = Column(Integer, ForeignKey('change_records.id'), comment='变化记录ID')
    
    # 通知信息
    notification_type = Column(String(50), nullable=False, comment='通知类型')
    recipient = Column(String(255), comment='接收者')
    subject = Column(String(500), comment='通知主题')
    content = Column(Text, comment='通知内容')
    
    # 发送状态
    status = Column(String(50), nullable=False, comment='发送状态')
    sent_at = Column(DateTime, comment='发送时间')
    error_message = Column(Text, comment='错误信息')
    retry_count = Column(Integer, default=0, comment='重试次数')
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    
    def __repr__(self):
        return f'<NotificationLog(id={self.id}, type="{self.notification_type}", status="{self.status}")>'