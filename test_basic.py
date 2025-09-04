#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础功能测试脚本
用于验证网页监控系统的核心组件是否正常工作
"""

import os
import sys
import time
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from monitor.config import Config
    from monitor.database import DatabaseManager, WebsiteModel, WebpageContentModel, ChangeDetectionModel
    from monitor.fetcher import RequestsFetcher, SeleniumFetcher
    from monitor.detector import HashDetector, DiffDetector
    from monitor.notifier import EmailNotifier
    from monitor.core import MonitorCore
except ImportError as e:
    print(f"❌ 导入模块失败: {e}")
    print("请确保已安装所有依赖包: pip install -r requirements.txt")
    sys.exit(1)


class BasicTester:
    """基础功能测试器"""
    
    def __init__(self):
        self.config_manager = None
        self.db_manager = None
        self.monitor_core = None
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, message: str = ""):
        """记录测试结果"""
        status = "✅" if success else "❌"
        result = f"{status} {test_name}"
        if message:
            result += f": {message}"
        print(result)
        self.test_results.append((test_name, success, message))
        
    def test_config_loading(self):
        """测试配置加载"""
        try:
            self.config_manager = Config()
            config = self.config_manager.get_config()
            
            # 检查关键配置项
            required_sections = ['database', 'celery', 'fetcher', 'detection', 'notification', 'storage', 'monitoring', 'web', 'logging']
            for section in required_sections:
                if section not in config:
                    raise ValueError(f"缺少配置节: {section}")
                    
            self.log_test("配置文件加载", True, "所有必需配置节都存在")
            return True
            
        except Exception as e:
            self.log_test("配置文件加载", False, str(e))
            return False
            
    def test_database_connection(self):
        """测试数据库连接"""
        try:
            # 使用SQLite进行测试，避免依赖外部数据库
            test_db_url = "sqlite:///test_monitor.db"
            self.db_manager = DatabaseManager(test_db_url)
            
            # 创建表
            self.db_manager.create_tables()
            
            # 测试基本操作
            with self.db_manager.get_session() as session:
                # 创建测试网站
                test_website = WebsiteModel(
                    name="测试网站",
                    url="https://httpbin.org/get",
                    interval_minutes=1,
                    monitor_type="content"
                )
                session.add(test_website)
                session.commit()
                
                # 查询测试
                websites = session.query(WebsiteModel).all()
                if len(websites) != 1:
                    raise ValueError("数据库操作失败")
                    
            self.log_test("数据库连接", True, "SQLite数据库操作正常")
            return True
            
        except Exception as e:
            self.log_test("数据库连接", False, str(e))
            return False
            
    def test_fetcher_functionality(self):
        """测试网页抓取功能"""
        try:
            # 测试requests抓取器
            requests_fetcher = RequestsFetcher()
            
            # 创建测试网站配置
            test_website = WebsiteModel(
                name="测试网站",
                url="https://httpbin.org/uuid",
                interval_minutes=1,
                monitor_type="content"
            )
            
            # 使用httpbin.org进行测试
            result = requests_fetcher.fetch_content(test_website.url, test_website)
            
            if not result or not result.get('success'):
                raise ValueError("抓取失败")
                
            content = result.get('raw_content', '') or result.get('extracted_content', '')
            if not content or len(content) < 10:
                raise ValueError("抓取内容为空或过短")
                
            # 检查是否包含预期的UUID内容
            if '"uuid"' not in content:
                raise ValueError("抓取内容不符合预期")
                
            self.log_test("网页抓取功能", True, f"成功抓取 {len(content)} 字符")
            return True
            
        except Exception as e:
            self.log_test("网页抓取功能", False, str(e))
            return False
            
    def test_detector_functionality(self):
        """测试变化检测功能"""
        try:
            # 测试哈希检测器
            hash_detector = HashDetector()
            
            # 创建测试网站配置
            test_website = WebsiteModel(
                name="测试网站",
                url="https://example.com",
                interval_minutes=1,
                monitor_type="content"
            )
            
            content1 = "这是第一个版本的内容"
            content2 = "这是第二个版本的内容"
            content3 = "这是第一个版本的内容"  # 与content1相同
            
            # 测试变化检测
            changes1 = hash_detector.detect_change(content1, content2, test_website)
            if not changes1.has_change:
                raise ValueError("应该检测到变化但没有检测到")
                
            # 测试无变化检测
            changes2 = hash_detector.detect_change(content1, content3, test_website)
            if changes2.has_change:
                raise ValueError("不应该检测到变化但检测到了")
                
            # 测试差异检测器
            diff_detector = DiffDetector()
            changes3 = diff_detector.detect_change(content1, content2, test_website)
            
            if not changes3.has_change:
                raise ValueError("差异检测器应该检测到变化")
                
            if not changes3.change_details:
                raise ValueError("差异检测器应该提供详细信息")
                
            self.log_test("变化检测功能", True, "哈希和差异检测都正常工作")
            return True
            
        except Exception as e:
            self.log_test("变化检测功能", False, str(e))
            return False
            
    def test_notification_functionality(self):
        """测试通知功能"""
        try:
            # 测试邮件通知器（不实际发送）
            email_config = {
                'smtp_host': 'smtp.example.com',
                'smtp_port': 587,
                'smtp_user': 'test@example.com',
                'smtp_password': 'password',
                'from_email': 'test@example.com',
                'from_name': '测试系统'
            }
            
            email_notifier = EmailNotifier(email_config)
            
            # 创建测试消息
            from monitor.notifier import NotificationMessage
            from datetime import datetime
            test_message = NotificationMessage(
                title="测试通知",
                content="这是一个测试通知消息",
                website_id=1,
                website_name="测试网站",
                website_url="https://example.com",
                change_type="content",
                change_score=0.8,
                change_summary="内容发生变化",
                timestamp=datetime.now()
            )
            
            # 验证消息格式化
            formatted = email_notifier._create_text_content(test_message)
            if not formatted or len(formatted) < 10:
                raise ValueError("消息格式化失败")
                
            self.log_test("通知功能", True, "消息格式化正常")
            return True
            
        except Exception as e:
            self.log_test("通知功能", False, str(e))
            return False
            
    def test_core_integration(self):
        """测试核心集成功能"""
        try:
            if not self.db_manager:
                raise ValueError("数据库管理器未初始化")
                
            # 创建监控核心实例，并确保使用测试数据库
            from monitor import database, core
            original_db_manager = database.db_manager
            database.db_manager = self.db_manager
            
            # 也需要替换core模块中的db_manager引用
            core.db_manager = self.db_manager
            
            self.monitor_core = MonitorCore()
            
            # 测试添加网站
            website_config = {
                'name': '集成测试网站',
                'url': 'https://httpbin.org/uuid',
                'interval_minutes': 1,
                'monitor_type': 'content',
                'use_selenium': False,
                'notification_emails': ['test@example.com'],
                'enabled': True
            }
            
            website_id = self.monitor_core.add_website(website_config)
            if not website_id:
                raise ValueError("添加网站失败")
                
            # 测试获取网站（使用新的会话确保数据已提交）
            website = self.db_manager.get_website(website_id)
            if not website:
                raise ValueError("获取网站失败：网站不存在")
            if website.name != website_config['name']:
                raise ValueError(f"获取网站失败：名称不匹配，期望'{website_config['name']}', 实际'{website.name}'")
                
            # 测试更新网站
            update_data = {'name': '更新后的网站名称'}
            success = self.monitor_core.update_website(website_id, update_data)
            if not success:
                raise ValueError("更新网站失败")
                
            # 验证更新
            updated_website = self.db_manager.get_website(website_id)
            if updated_website.name != update_data['name']:
                raise ValueError("网站更新验证失败")
                
            self.log_test("核心集成功能", True, "网站CRUD操作正常")
            return True
            
        except Exception as e:
            self.log_test("核心集成功能", False, str(e))
            return False
            
    def test_manual_check(self):
        """测试手动检查功能"""
        try:
            if not self.monitor_core:
                raise ValueError("监控核心未初始化")
                
            # 获取测试网站
            with self.db_manager.get_session() as session:
                website = session.query(WebsiteModel).first()
                if not website:
                    raise ValueError("没有找到测试网站")
                    
                # 直接使用WebpageFetcher进行同步测试，避免异步任务的复杂性
                from monitor.fetcher import WebpageFetcher
                from monitor import database, fetcher
                
                # 临时替换全局db_manager为测试实例
                original_db_manager = database.db_manager
                database.db_manager = self.db_manager
                fetcher.db_manager = self.db_manager
                
                try:
                    fetcher_instance = WebpageFetcher()
                    result = fetcher_instance.fetch_website(website.id)
                finally:
                    # 恢复原始db_manager
                    database.db_manager = original_db_manager
                    fetcher.db_manager = original_db_manager
                
                print(f"Debug: 抓取网站ID={website.id}, 结果={result}")
                
                if not result.get('success'):
                    raise ValueError(f"网页抓取失败: {result.get('error', '未知错误')}")
                    
            # 验证是否创建了内容记录（在新的会话中查询）
            with self.db_manager.get_session() as session:
                content_count = session.query(WebpageContentModel).filter_by(website_id=website.id).count()
                total_content_count = session.query(WebpageContentModel).count()
                print(f"Debug: 网站ID={website.id}的内容记录数={content_count}, 总内容记录数={total_content_count}")
                if content_count == 0:
                    raise ValueError("没有创建内容记录")
                    
            self.log_test("手动检查功能", True, "手动检查和内容记录正常")
            return True
            
        except Exception as e:
            self.log_test("手动检查功能", False, str(e))
            return False
            
    def cleanup(self):
        """清理测试数据"""
        try:
            # 删除测试数据库文件
            test_db_file = Path("test_monitor.db")
            if test_db_file.exists():
                test_db_file.unlink()
                
            self.log_test("清理测试数据", True, "测试数据已清理")
            
        except Exception as e:
            self.log_test("清理测试数据", False, str(e))
            
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始运行网页监控系统基础功能测试...\n")
        
        tests = [
            self.test_config_loading,
            self.test_database_connection,
            self.test_fetcher_functionality,
            self.test_detector_functionality,
            self.test_notification_functionality,
            self.test_core_integration,
            self.test_manual_check,
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                if test():
                    passed += 1
            except Exception as e:
                print(f"❌ 测试执行异常: {e}")
                
        # 清理
        self.cleanup()
        
        # 输出测试结果摘要
        print(f"\n📊 测试结果摘要:")
        print(f"总测试数: {total}")
        print(f"通过数: {passed}")
        print(f"失败数: {total - passed}")
        print(f"通过率: {passed/total*100:.1f}%")
        
        if passed == total:
            print("\n🎉 所有测试通过！系统基础功能正常。")
            return True
        else:
            print("\n⚠️  部分测试失败，请检查相关组件。")
            return False
            
    def print_system_info(self):
        """打印系统信息"""
        print("📋 系统信息:")
        print(f"Python版本: {sys.version}")
        print(f"操作系统: {os.name}")
        print(f"工作目录: {os.getcwd()}")
        print(f"项目根目录: {project_root}")
        print()


def main():
    """主函数"""
    tester = BasicTester()
    
    # 打印系统信息
    tester.print_system_info()
    
    # 运行测试
    success = tester.run_all_tests()
    
    # 返回适当的退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()