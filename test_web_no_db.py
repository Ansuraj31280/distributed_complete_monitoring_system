#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Web服务器在跳过数据库检查时是否能正常启动
"""

import os
import sys
import logging
import importlib.util
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 设置环境变量，跳过数据库检查
os.environ['SKIP_DB_CHECK'] = 'true'

# 禁止导入数据库模块
sys.modules['monitor.database'] = None

def main():
    """主函数"""
    # 导入Flask应用
    try:
        from monitor.web import app
        logger.info("Flask应用导入成功")
        
        # 测试应用是否可以启动
        logger.info("测试应用是否可以启动...")
        app.test_client().get('/')
        logger.info("应用启动成功")
        
        # 测试健康检查API
        logger.info("测试健康检查API...")
        response = app.test_client().get('/api/health')
        logger.info(f"健康检查API响应: {response.status_code} {response.data}")
        
        return True
    except Exception as e:
        logger.error(f"测试失败: {e}")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)