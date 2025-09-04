#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的Web服务器，不依赖数据库
"""

import os
import json
import datetime
from flask import Flask, jsonify, render_template_string

# 创建Flask应用
app = Flask(__name__)
app.secret_key = 'simple_web_server_key'

# 简单的HTML模板
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>监控系统 - 仪表板</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
        h1 { color: #333; }
        .card { border: 1px solid #ddd; border-radius: 4px; padding: 15px; margin-bottom: 15px; }
        .status { display: inline-block; padding: 5px 10px; border-radius: 3px; color: white; }
        .status-ok { background-color: #4CAF50; }
        .status-error { background-color: #F44336; }
    </style>
</head>
<body>
    <h1>系统仪表板</h1>
    
    <div class="card">
        <h2>系统状态</h2>
        <p><span class="status status-ok">运行中</span></p>
        <p>启动时间: {{ start_time }}</p>
        <p>数据库状态: {{ db_status }}</p>
    </div>
    
    <div class="card">
        <h2>API接口</h2>
        <ul>
            <li><a href="/api/health">健康检查</a></li>
        </ul>
    </div>
</body>
</html>
"""

# 记录启动时间
START_TIME = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@app.route('/')
def index():
    """首页"""
    return render_template_string(DASHBOARD_TEMPLATE, 
                                 start_time=START_TIME,
                                 db_status="未连接 (跳过数据库检查)")

@app.route('/dashboard')
def dashboard():
    """仪表板"""
    return render_template_string(DASHBOARD_TEMPLATE, 
                                 start_time=START_TIME,
                                 db_status="未连接 (跳过数据库检查)")

@app.route('/api/health')
def api_health():
    """健康检查API"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.datetime.now().isoformat(),
        'database_available': False,
        'skip_db_check': True,
        'uptime': str(datetime.datetime.now() - datetime.datetime.strptime(START_TIME, "%Y-%m-%d %H:%M:%S"))
    })

@app.route('/api/settings/general', methods=['GET'])
def api_settings_general_get():
    """获取通用设置"""
    return jsonify({
        'status': 'ok',
        'settings': {
            'logging': {
                'level': 'info',
                'file_enabled': True,
                'console_enabled': True
            },
            'notification': {
                'email_enabled': False,
                'webhook_enabled': False
            },
            'security': {
                'require_login': True,
                'session_timeout': 3600
            }
        }
    })

@app.route('/api/settings/general', methods=['POST'])
def api_settings_general_post():
    """更新通用设置"""
    return jsonify({
        'status': 'ok',
        'message': '设置已更新'
    })

@app.route('/api/test/database')
def api_test_database():
    """测试数据库连接"""
    return jsonify({
        'status': 'error',
        'message': '数据库连接失败: 跳过数据库检查模式'
    })

@app.route('/api/system/info')
def api_system_info():
    """获取系统信息"""
    return jsonify({
        'status': 'ok',
        'system_info': {
            'version': '1.0.0',
            'python_version': '3.10.0',
            'platform': 'Windows',
            'database_type': 'None',
            'uptime': str(datetime.datetime.now() - datetime.datetime.strptime(START_TIME, "%Y-%m-%d %H:%M:%S")),
            'memory_usage': '50MB',
            'cpu_usage': '5%'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)