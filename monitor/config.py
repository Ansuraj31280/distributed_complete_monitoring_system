# 配置管理模块

import os
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from loguru import logger


@dataclass
class DatabaseConfig:
    """数据库配置"""
    postgresql_host: str
    postgresql_port: int
    postgresql_database: str
    postgresql_username: str
    postgresql_password: str
    postgresql_pool_size: int
    postgresql_max_overflow: int
    redis_host: str
    redis_port: int
    redis_db: int
    redis_password: Optional[str]
    redis_max_connections: int


@dataclass
class CeleryConfig:
    """Celery任务队列配置"""
    broker_url: str
    result_backend: str
    task_serializer: str
    accept_content: list
    result_serializer: str
    timezone: str
    enable_utc: bool
    worker_concurrency: int
    task_routes: Dict[str, Dict[str, str]]


@dataclass
class FetcherConfig:
    """网页抓取配置"""
    timeout: int
    max_retries: int
    retry_delay: int
    concurrent_requests: int
    user_agents: list
    proxies_enabled: bool
    proxies_pool: list
    selenium_enabled: bool
    selenium_driver_path: str
    selenium_headless: bool
    selenium_window_size: str
    selenium_page_load_timeout: int


@dataclass
class DetectionConfig:
    """变化检测配置"""
    text_similarity: float
    structure_similarity: float
    image_similarity: float
    ignore_patterns: list
    high_priority_interval: int
    medium_priority_interval: int
    low_priority_interval: int


@dataclass
class NotificationConfig:
    """通知配置"""
    email_enabled: bool
    email_smtp_server: str
    email_smtp_port: int
    email_username: str
    email_password: str
    email_from_address: str
    webhook_enabled: bool
    webhook_urls: list
    dingtalk_enabled: bool
    dingtalk_webhook_url: str
    dingtalk_secret: str


@dataclass
class StorageConfig:
    """存储配置"""
    raw_data_retention_days: int
    change_history_retention_days: int
    logs_retention_days: int
    webpage_content_cache_ttl: int
    detection_result_cache_ttl: int


@dataclass
class MonitoringConfig:
    """系统监控配置"""
    cpu_threshold: int
    memory_threshold: int
    disk_threshold: int
    max_queue_size: int
    max_processing_time: int
    failure_rate_threshold: float


@dataclass
class WebConfig:
    """Web界面配置"""
    host: str
    port: int
    debug: bool
    secret_key: str
    admin_username: str = "admin"
    admin_password: str = "admin123"


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str
    format: str
    rotation: str
    retention: str
    compression: str


@dataclass
class SecurityConfig:
    """安全配置"""
    api_rate_limit_per_minute: int = 100
    allowed_ips: str = ""
    https_only: bool = False
    enable_csrf_protection: bool = True


class Config:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._find_config_file()
        self._config_data = self._load_config()
        self._parse_config()
        
    def _find_config_file(self) -> str:
        """查找配置文件"""
        possible_paths = [
            "config.yaml",
            "config.yml", 
            "./config.yaml",
            "./config.yml",
            os.path.join(os.path.dirname(__file__), "..", "config.yaml"),
            os.path.join(os.path.dirname(__file__), "..", "config.yml")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
                
        raise FileNotFoundError("找不到配置文件，请确保config.yaml存在")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            logger.info(f"配置文件加载成功: {self.config_path}")
            return config_data
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            raise
    
    def _parse_config(self):
        """解析配置数据"""
        try:
            # 数据库配置
            db_config = self._config_data['database']
            self.database = DatabaseConfig(
                postgresql_host=db_config['postgresql']['host'],
                postgresql_port=db_config['postgresql']['port'],
                postgresql_database=db_config['postgresql']['database'],
                postgresql_username=db_config['postgresql']['username'],
                postgresql_password=db_config['postgresql']['password'],
                postgresql_pool_size=db_config['postgresql']['pool_size'],
                postgresql_max_overflow=db_config['postgresql']['max_overflow'],
                redis_host=db_config['redis']['host'],
                redis_port=db_config['redis']['port'],
                redis_db=db_config['redis']['db'],
                redis_password=db_config['redis']['password'],
                redis_max_connections=db_config['redis']['max_connections']
            )
            
            # Celery配置
            celery_config = self._config_data['celery']
            self.celery = CeleryConfig(
                broker_url=celery_config['broker_url'],
                result_backend=celery_config['result_backend'],
                task_serializer=celery_config['task_serializer'],
                accept_content=celery_config['accept_content'],
                result_serializer=celery_config['result_serializer'],
                timezone=celery_config['timezone'],
                enable_utc=celery_config['enable_utc'],
                worker_concurrency=celery_config['worker_concurrency'],
                task_routes=celery_config['task_routes']
            )
            
            # 抓取配置
            fetcher_config = self._config_data['fetcher']
            self.fetcher = FetcherConfig(
                timeout=fetcher_config['timeout'],
                max_retries=fetcher_config['max_retries'],
                retry_delay=fetcher_config['retry_delay'],
                concurrent_requests=fetcher_config['concurrent_requests'],
                user_agents=fetcher_config['user_agents'],
                proxies_enabled=fetcher_config['proxies']['enabled'],
                proxies_pool=fetcher_config['proxies']['pool'],
                selenium_enabled=fetcher_config['selenium']['enabled'],
                selenium_driver_path=fetcher_config['selenium']['driver_path'],
                selenium_headless=fetcher_config['selenium']['headless'],
                selenium_window_size=fetcher_config['selenium']['window_size'],
                selenium_page_load_timeout=fetcher_config['selenium']['page_load_timeout']
            )
            
            # 检测配置
            detection_config = self._config_data['detection']
            self.detection = DetectionConfig(
                text_similarity=detection_config['algorithms']['text_similarity'],
                structure_similarity=detection_config['algorithms']['structure_similarity'],
                image_similarity=detection_config['algorithms']['image_similarity'],
                ignore_patterns=detection_config['ignore_patterns'],
                high_priority_interval=detection_config['intervals']['high_priority'],
                medium_priority_interval=detection_config['intervals']['medium_priority'],
                low_priority_interval=detection_config['intervals']['low_priority']
            )
            
            # 通知配置
            notification_config = self._config_data['notification']
            self.notification = NotificationConfig(
                email_enabled=notification_config['email']['enabled'],
                email_smtp_server=notification_config['email']['smtp_server'],
                email_smtp_port=notification_config['email']['smtp_port'],
                email_username=notification_config['email']['username'],
                email_password=notification_config['email']['password'],
                email_from_address=notification_config['email']['from_address'],
                webhook_enabled=notification_config['webhook']['enabled'],
                webhook_urls=notification_config['webhook']['urls'],
                dingtalk_enabled=notification_config['dingtalk']['enabled'],
                dingtalk_webhook_url=notification_config['dingtalk']['webhook_url'],
                dingtalk_secret=notification_config['dingtalk']['secret']
            )
            
            # 存储配置
            storage_config = self._config_data['storage']
            self.storage = StorageConfig(
                raw_data_retention_days=storage_config['retention']['raw_data_days'],
                change_history_retention_days=storage_config['retention']['change_history_days'],
                logs_retention_days=storage_config['retention']['logs_days'],
                webpage_content_cache_ttl=storage_config['cache']['webpage_content_ttl'],
                detection_result_cache_ttl=storage_config['cache']['detection_result_ttl']
            )
            
            # 监控配置
            monitoring_config = self._config_data['monitoring']
            self.monitoring = MonitoringConfig(
                cpu_threshold=monitoring_config['system']['cpu_threshold'],
                memory_threshold=monitoring_config['system']['memory_threshold'],
                disk_threshold=monitoring_config['system']['disk_threshold'],
                max_queue_size=monitoring_config['tasks']['max_queue_size'],
                max_processing_time=monitoring_config['tasks']['max_processing_time'],
                failure_rate_threshold=monitoring_config['tasks']['failure_rate_threshold']
            )
            
            # Web配置
            web_config = self._config_data['web']
            self.web = WebConfig(
                host=web_config['host'],
                port=web_config['port'],
                debug=web_config['debug'],
                secret_key=web_config['secret_key']
            )
            
            # 日志配置
            logging_config = self._config_data['logging']
            self.logging = LoggingConfig(
                level=logging_config['level'],
                format=logging_config['format'],
                rotation=logging_config['rotation'],
                retention=logging_config['retention'],
                compression=logging_config['compression']
            )
            
            # 安全配置
            self.security = SecurityConfig()
            if 'security' in self._config_data:
                security_config = self._config_data['security']
                if 'api' in security_config and 'rate_limiting' in security_config['api']:
                    self.security.api_rate_limit_per_minute = security_config.get('api', {}).get('rate_limit_per_minute', 100)
                if 'authentication' in security_config and 'allowed_ips' in security_config['authentication']:
                    self.security.allowed_ips = security_config.get('authentication', {}).get('allowed_ips', '')
                if 'api' in security_config and 'https_only' in security_config['api']:
                    self.security.https_only = security_config.get('api', {}).get('https_only', False)
                if 'api' in security_config and 'enable_csrf_protection' in security_config['api']:
                    self.security.enable_csrf_protection = security_config.get('api', {}).get('enable_csrf_protection', True)
            
            logger.info("配置解析完成")
            
        except Exception as e:
            logger.error(f"配置解析失败: {e}")
            raise
    
    def get_config(self) -> Dict[str, Any]:
        """获取完整配置数据"""
        return self._config_data
    
    def get_database_url(self) -> str:
        """获取PostgreSQL数据库连接URL"""
        return (f"postgresql://{self.database.postgresql_username}:"
                f"{self.database.postgresql_password}@"
                f"{self.database.postgresql_host}:"
                f"{self.database.postgresql_port}/"
                f"{self.database.postgresql_database}")
    
    def get_redis_url(self) -> str:
        """获取Redis连接URL"""
        if self.database.redis_password:
            return (f"redis://:{self.database.redis_password}@"
                   f"{self.database.redis_host}:"
                   f"{self.database.redis_port}/"
                   f"{self.database.redis_db}")
        else:
            return (f"redis://{self.database.redis_host}:"
                   f"{self.database.redis_port}/"
                   f"{self.database.redis_db}")
    
    def reload(self):
        """重新加载配置"""
        self._config_data = self._load_config()
        self._parse_config()
        logger.info("配置重新加载完成")


# 全局配置实例
# 延迟初始化，避免在跳过数据库检查时出错
config = None

def get_config():
    """获取全局配置实例"""
    global config
    if config is None:
        config = Config()
    return config

# 为了向后兼容，在非跳过数据库检查时立即初始化
# 但是为了避免在导入时触发数据库连接，我们延迟初始化
# if not os.environ.get('SKIP_DB_CHECK', '').lower() == 'true':
#     config = Config()