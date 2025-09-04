#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网页监控系统主程序入口

这个文件是整个监控系统的启动入口，提供了多种运行模式：
- web: 启动Web管理界面
- worker: 启动Celery工作进程
- beat: 启动Celery定时任务调度器
- monitor: 启动完整的监控系统（包含所有组件）
- shell: 启动交互式Shell
"""

import os
import sys
import argparse
import logging
import signal
import time
from pathlib import Path
from typing import Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 延迟导入，避免在设置环境变量前导入数据库模块
# 这些模块将在需要时导入

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('monitor.log')
    ]
)
logger = logging.getLogger(__name__)


class MonitorApplication:
    """监控应用程序主类"""
    
    def __init__(self):
        self.config = None
        self.core: Optional['MonitorCore'] = None
        self.running = False
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，开始优雅关闭...")
        self.running = False
        if self.core:
            self.core.stop()
        # 对于Web模式，让Flask自己处理退出
        sys.exit(0)
    
    def run_web(self, host: str = '0.0.0.0', port: int = 5000, debug: bool = False, skip_db_check: bool = False):
        """启动Web管理界面"""
        logger.info("启动Web管理界面...")
        
        try:
            if skip_db_check:
                logger.info("跳过数据库连接检查")
                # 先设置环境变量，表示跳过数据库检查
                os.environ['SKIP_DB_CHECK'] = 'true'
                
                # 跳过数据库检查模式 - 使用原有的Web界面但跳过数据库初始化
                from monitor.web import app, create_app
                from monitor.core import MonitorCore
                
                # 创建一个空的核心实例用于Web应用
                self.core = MonitorCore()
                
                # 创建Flask应用
                web_app = create_app(self.core)
                
                logger.info(f"开发模式Web服务器启动在 http://{host}:{port}")
                # 启动Web服务器
                web_app.run(host=host, port=port, debug=debug, use_reloader=False)
            else:
                # 导入必要的模块
                from monitor.core import MonitorCore
                from monitor.web import create_app
                from monitor.config import Config
                
                # 初始化配置
                if self.config is None:
                    self.config = Config()
                
                # 初始化核心组件
                self.core = MonitorCore(self.config)
                self.core.start()
                
                # 创建Flask应用
                app = create_app(self.core)
                
                logger.info(f"Web服务器启动在 http://{host}:{port}")
                # 启动Web服务器
                app.run(host=host, port=port, debug=debug, use_reloader=False)
            
        except Exception as e:
            logger.error(f"启动Web界面失败: {e}")
            sys.exit(1)
        finally:
            if self.core:
                self.core.stop()
    
    def run_worker(self, concurrency: int = 4, queues: str = 'default'):
        """启动Celery工作进程"""
        logger.info(f"启动Celery工作进程 (并发数: {concurrency}, 队列: {queues})...")
        
        try:
            # 导入必要的模块
            from monitor.scheduler import TaskScheduler
            from monitor.config import Config
            
            # 初始化配置
            if self.config is None:
                self.config = Config()
            
            # 初始化任务调度器
            scheduler = TaskScheduler(self.config)
            
            # 启动工作进程
            scheduler.start_worker(
                concurrency=concurrency,
                queues=queues.split(',')
            )
            
        except Exception as e:
            logger.error(f"启动工作进程失败: {e}")
            sys.exit(1)
    
    def run_beat(self):
        """启动Celery定时任务调度器"""
        logger.info("启动Celery定时任务调度器...")
        
        try:
            # 导入必要的模块
            from monitor.scheduler import TaskScheduler
            from monitor.config import Config
            
            # 初始化配置
            if self.config is None:
                self.config = Config()
            
            # 初始化任务调度器
            scheduler = TaskScheduler(self.config)
            
            # 启动定时任务调度器
            scheduler.start_beat()
            
        except Exception as e:
            logger.error(f"启动定时任务调度器失败: {e}")
            sys.exit(1)
    
    def run_monitor(self):
        """启动完整的监控系统"""
        logger.info("启动完整监控系统...")
        
        try:
            # 导入必要的模块
            from monitor.core import MonitorCore
            from monitor.config import Config
            
            # 初始化配置
            if self.config is None:
                self.config = Config()
            
            # 初始化核心组件
            self.core = MonitorCore(self.config)
            self.core.start()
            
            self.running = True
            logger.info("监控系统启动成功，按 Ctrl+C 停止")
            
            # 主循环
            while self.running:
                try:
                    time.sleep(1)
                except KeyboardInterrupt:
                    break
            
        except Exception as e:
            logger.error(f"启动监控系统失败: {e}")
            sys.exit(1)
        finally:
            if self.core:
                self.core.stop()
    
    def run_shell(self):
        """启动交互式Shell"""
        logger.info("启动交互式Shell...")
        
        try:
            # 导入必要的模块
            from monitor.core import MonitorCore
            from monitor.database import DatabaseManager
            from monitor.scheduler import TaskScheduler
            from monitor.config import Config
            
            # 初始化配置
            if self.config is None:
                self.config = Config()
            
            # 初始化组件
            config = self.config
            db_manager = DatabaseManager(config)
            scheduler = TaskScheduler(config)
            core = MonitorCore(config)
            
            # 导入常用模块
            import IPython
            from monitor.models import WebsiteModel, WebpageContentModel, ChangeDetectionModel
            from monitor.tasks import fetch_website_task, detect_changes_task
            
            # 准备Shell环境
            shell_vars = {
                'config': config,
                'db_manager': db_manager,
                'scheduler': scheduler,
                'core': core,
                'WebsiteModel': WebsiteModel,
                'WebpageContentModel': WebpageContentModel,
                'ChangeDetectionModel': ChangeDetectionModel,
                'fetch_website_task': fetch_website_task,
                'detect_changes_task': detect_changes_task,
            }
            
            print("\n=== 网页监控系统交互式Shell ===")
            print("可用对象:")
            for name, obj in shell_vars.items():
                print(f"  {name}: {type(obj).__name__}")
            print("\n使用 exit() 或 Ctrl+D 退出\n")
            
            # 启动IPython Shell
            IPython.start_ipython(argv=[], user_ns=shell_vars)
            
        except ImportError:
            # 如果没有IPython，使用标准Python Shell
            import code
            code.interact(local=shell_vars)
        except Exception as e:
            logger.error(f"启动Shell失败: {e}")
            sys.exit(1)
    
    def init_database(self):
        """初始化数据库"""
        logger.info("初始化数据库...")
        
        try:
            # 导入必要的模块
            from monitor.database import DatabaseManager
            from monitor.config import Config
            
            # 初始化配置
            if self.config is None:
                self.config = Config()
            
            db_manager = DatabaseManager(self.config)
            db_manager.init_database()
            logger.info("数据库初始化完成")
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            sys.exit(1)
    
    def check_dependencies(self):
        """检查系统依赖"""
        logger.info("检查系统依赖...")
        
        try:
            # 检查Python版本
            if sys.version_info < (3, 8):
                logger.error("需要Python 3.8或更高版本")
                return False
            
            # 检查必需的包
            required_packages = [
                'flask', 'celery', 'sqlalchemy', 'psycopg2', 'redis',
                'requests', 'selenium', 'beautifulsoup4', 'lxml',
                'pyyaml', 'jinja2', 'werkzeug'
            ]
            
            missing_packages = []
            for package in required_packages:
                try:
                    __import__(package)
                except ImportError:
                    missing_packages.append(package)
            
            if missing_packages:
                logger.error(f"缺少必需的包: {', '.join(missing_packages)}")
                logger.error("请运行: pip install -r requirements.txt")
                return False
            
            # 检查数据库连接
            try:
                # 导入必要的模块
                from monitor.database import DatabaseManager
                from monitor.config import Config
                
                # 初始化配置
                if self.config is None:
                    self.config = Config()
                
                db_manager = DatabaseManager(self.config)
                db_manager.test_connection()
                logger.info("数据库连接正常")
            except Exception as e:
                logger.warning(f"数据库连接失败: {e}")
            
            # 检查Redis连接
            try:
                scheduler = TaskScheduler(self.config)
                scheduler.test_connection()
                logger.info("Redis连接正常")
            except Exception as e:
                logger.warning(f"Redis连接失败: {e}")
            
            logger.info("依赖检查完成")
            return True
            
        except Exception as e:
            logger.error(f"依赖检查失败: {e}")
            return False
    
    def show_status(self):
        """显示系统状态"""
        logger.info("获取系统状态...")
        
        try:
            # 初始化组件
            db_manager = DatabaseManager(self.config)
            scheduler = TaskScheduler(self.config)
            
            print("\n=== 网页监控系统状态 ===")
            
            # 数据库状态
            try:
                db_manager.test_connection()
                print("✓ 数据库: 连接正常")
                
                # 获取统计信息
                with db_manager.get_session() as session:
                    from monitor.models import WebsiteModel, WebpageContentModel
                    website_count = session.query(WebsiteModel).count()
                    content_count = session.query(WebpageContentModel).count()
                    print(f"  - 监控网站数: {website_count}")
                    print(f"  - 内容记录数: {content_count}")
                    
            except Exception as e:
                print(f"✗ 数据库: 连接失败 ({e})")
            
            # Redis状态
            try:
                scheduler.test_connection()
                print("✓ Redis: 连接正常")
                
                # 获取队列状态
                queue_status = scheduler.get_queue_status()
                for queue_name, status in queue_status.items():
                    print(f"  - 队列 {queue_name}: {status['length']} 个任务")
                    
            except Exception as e:
                print(f"✗ Redis: 连接失败 ({e})")
            
            # 工作进程状态
            try:
                worker_status = scheduler.get_worker_status()
                active_workers = len([w for w in worker_status if w['status'] == 'online'])
                print(f"✓ 工作进程: {active_workers} 个活跃")
                
                for worker in worker_status:
                    status_icon = "✓" if worker['status'] == 'online' else "✗"
                    print(f"  {status_icon} {worker['name']}: {worker['status']}")
                    
            except Exception as e:
                print(f"✗ 工作进程: 获取状态失败 ({e})")
            
            print("\n")
            
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='网页监控系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s web                    # 启动Web管理界面
  %(prog)s worker                 # 启动工作进程
  %(prog)s beat                   # 启动定时任务调度器
  %(prog)s monitor                # 启动完整监控系统
  %(prog)s shell                  # 启动交互式Shell
  %(prog)s init-db                # 初始化数据库
  %(prog)s check                  # 检查系统依赖
  %(prog)s status                 # 显示系统状态
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # Web命令
    web_parser = subparsers.add_parser('web', help='启动Web管理界面')
    web_parser.add_argument('--host', default='0.0.0.0', help='绑定主机地址')
    web_parser.add_argument('--port', type=int, default=5000, help='绑定端口')
    web_parser.add_argument('--debug', action='store_true', help='启用调试模式')
    web_parser.add_argument('--skip-db-check', action='store_true', help='跳过数据库连接检查')
    
    # Worker命令
    worker_parser = subparsers.add_parser('worker', help='启动Celery工作进程')
    worker_parser.add_argument('--concurrency', type=int, default=4, help='并发数')
    worker_parser.add_argument('--queues', default='default', help='队列名称（逗号分隔）')
    worker_parser.add_argument('--skip-db-check', action='store_true', help='跳过数据库连接检查')
    
    # Beat命令
    beat_parser = subparsers.add_parser('beat', help='启动Celery定时任务调度器')
    beat_parser.add_argument('--skip-db-check', action='store_true', help='跳过数据库连接检查')
    
    # Monitor命令
    monitor_parser = subparsers.add_parser('monitor', help='启动完整监控系统')
    monitor_parser.add_argument('--skip-db-check', action='store_true', help='跳过数据库连接检查')
    
    # Shell命令
    shell_parser = subparsers.add_parser('shell', help='启动交互式Shell')
    shell_parser.add_argument('--skip-db-check', action='store_true', help='跳过数据库连接检查')
    
    # 初始化数据库命令
    subparsers.add_parser('init-db', help='初始化数据库')
    
    # 检查依赖命令
    check_parser = subparsers.add_parser('check', help='检查系统依赖')
    check_parser.add_argument('--skip-db-check', action='store_true', help='跳过数据库连接检查')
    
    # 状态命令
    status_parser = subparsers.add_parser('status', help='显示系统状态')
    status_parser.add_argument('--skip-db-check', action='store_true', help='跳过数据库连接检查')
    
    # 解析参数
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 创建应用实例
    app = MonitorApplication()
    
    # 执行命令
    try:
        if args.command == 'web':
            app.run_web(host=args.host, port=args.port, debug=args.debug, skip_db_check=args.skip_db_check)
        elif args.command == 'worker':
            app.run_worker(concurrency=args.concurrency, queues=args.queues)
        elif args.command == 'beat':
            app.run_beat()
        elif args.command == 'monitor':
            app.run_monitor()
        elif args.command == 'shell':
            app.run_shell()
        elif args.command == 'init-db':
            app.init_database()
        elif args.command == 'check':
            if not app.check_dependencies():
                sys.exit(1)
        elif args.command == 'status':
            app.show_status()
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        logger.info("用户中断操作")
    except Exception as e:
        logger.error(f"执行命令失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()