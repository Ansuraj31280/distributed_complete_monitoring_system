# 网页监控系统

一个功能强大的分布式网页内容监控系统，支持海量网页并发监控、智能变化检测和多种通知方式。

## 🚀 功能特性

### 核心功能
- **海量并发监控**: 基于Celery分布式任务队列，支持数万个网页同时监控
- **智能变化检测**: 支持文本、结构化数据和图片的多维度变化检测
- **多种抓取方式**: 支持requests和Selenium两种抓取方式，应对各种网页类型
- **反爬虫机制**: 内置User-Agent轮换、代理支持、随机延迟等反检测功能
- **实时通知**: 支持邮件、钉钉、Webhook等多种通知方式
- **Web管理界面**: 现代化的Web界面，支持可视化配置和监控

### 高级特性
- **语义变化检测**: 基于机器学习的智能内容分析
- **数据持久化**: PostgreSQL + Redis双重存储保障
- **任务调度**: 灵活的定时任务和手动触发机制
- **系统监控**: 实时系统资源监控和性能统计
- **安全认证**: 用户登录、权限控制和API安全
- **配置管理**: 支持配置导入导出和热更新

## 📋 系统要求

- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- Chrome/Chromium (用于Selenium)

## 🛠️ 安装部署

### 1. 克隆项目
```bash
git clone <repository-url>
cd web-monitor
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境
创建 `.env` 文件：
```env
# 数据库配置
DATABASE_URL=postgresql://username:password@localhost:5432/monitor

# Redis配置
REDIS_URL=redis://localhost:6379/0

# 邮件配置
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# 钉钉配置
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
DINGTALK_SECRET=your-secret

# 安全配置
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
```

### 4. 初始化数据库
```bash
python main.py init-db
```

### 5. 检查系统依赖
```bash
python main.py check
```

## 🚀 启动系统

### 方式一：完整启动（推荐用于开发）
```bash
python main.py monitor
```

### 方式二：分组件启动（推荐用于生产）

1. 启动Web界面：
```bash
python main.py web --host 0.0.0.0 --port 5000
```

2. 启动工作进程：
```bash
python main.py worker --concurrency 4
```

3. 启动定时任务调度器：
```bash
python main.py beat
```

### 方式三：使用Docker（推荐用于生产）
```bash
# 构建镜像
docker build -t web-monitor .

# 启动服务
docker-compose up -d
```

## 📖 使用指南

### Web界面访问
启动后访问 `http://localhost:5000`，使用默认账户登录：
- 用户名: `admin`
- 密码: `admin123`

### 添加监控网站

1. 登录Web界面
2. 点击「添加网站」
3. 填写网站信息：
   - **网站名称**: 便于识别的名称
   - **URL**: 要监控的网页地址
   - **检查间隔**: 监控频率（分钟）
   - **检测算法**: 选择变化检测方式
   - **CSS选择器**: 指定监控的页面元素（可选）
   - **通知设置**: 配置变化通知方式

### 检测算法说明

- **哈希检测**: 快速检测，适用于整页内容监控
- **差异检测**: 详细对比，显示具体变化内容
- **语义检测**: 智能分析，过滤无意义变化

### 命令行工具

```bash
# 查看系统状态
python main.py status

# 启动交互式Shell
python main.py shell

# 导出配置
python main.py export-config

# 导入配置
python main.py import-config config.yaml
```

## 🔧 配置说明

### 系统配置文件
配置文件位于 `config/config.yaml`，主要配置项：

```yaml
# 系统设置
system:
  name: "网页监控系统"
  timezone: "Asia/Shanghai"
  log_level: "INFO"
  
# 数据库设置
database:
  host: "localhost"
  port: 5432
  name: "monitor"
  user: "monitor"
  password: "password"
  
# Redis设置
redis:
  host: "localhost"
  port: 6379
  db: 0
  
# 监控设置
monitoring:
  max_concurrent_fetches: 10
  request_timeout: 30
  user_agent_rotation: true
  proxy_rotation: false
  
# 通知设置
notification:
  rate_limit:
    cooldown_minutes: 30
    max_per_hour: 10
```

### 网站配置示例

```python
# 通过API添加网站
import requests

website_config = {
    "name": "示例网站",
    "url": "https://example.com",
    "check_interval": 60,
    "detection_algorithm": "semantic",
    "css_selector": ".content",
    "use_selenium": False,
    "notification_emails": ["admin@example.com"],
    "notification_threshold": 0.1,
    "headers": {
        "User-Agent": "Mozilla/5.0..."
    },
    "cookies": {
        "session": "abc123"
    }
}

response = requests.post(
    "http://localhost:5000/api/websites",
    json=website_config,
    headers={"Authorization": "Bearer your-token"}
)
```

## 📊 监控和运维

### 系统监控
- **资源监控**: CPU、内存、磁盘使用率
- **任务监控**: 队列长度、执行状态、错误率
- **性能监控**: 响应时间、吞吐量统计

### 日志管理
- **应用日志**: `logs/app.log`
- **任务日志**: `logs/celery.log`
- **错误日志**: `logs/error.log`

### 数据备份
```bash
# 备份数据库
pg_dump monitor > backup_$(date +%Y%m%d).sql

# 备份配置
tar -czf config_backup_$(date +%Y%m%d).tar.gz config/
```

### 性能优化

1. **数据库优化**:
   - 定期清理历史数据
   - 添加适当索引
   - 调整连接池大小

2. **Redis优化**:
   - 配置内存淘汰策略
   - 启用持久化
   - 监控内存使用

3. **工作进程优化**:
   - 根据CPU核心数调整并发数
   - 设置合适的任务超时时间
   - 启用任务结果压缩

## 🔌 API文档

### 认证
所有API请求需要在Header中包含认证令牌：
```
Authorization: Bearer <your-token>
```

### 网站管理

#### 获取网站列表
```http
GET /api/websites
```

#### 添加网站
```http
POST /api/websites
Content-Type: application/json

{
  "name": "网站名称",
  "url": "https://example.com",
  "check_interval": 60
}
```

#### 更新网站
```http
PUT /api/websites/{id}
Content-Type: application/json

{
  "name": "新名称",
  "check_interval": 30
}
```

#### 删除网站
```http
DELETE /api/websites/{id}
```

#### 手动检查
```http
POST /api/websites/{id}/check
```

### 任务管理

#### 获取任务状态
```http
GET /api/tasks/{task_id}
```

#### 获取队列状态
```http
GET /api/queues
```

### 系统信息

#### 获取系统状态
```http
GET /api/system/status
```

#### 获取统计信息
```http
GET /api/system/stats
```

## 🧪 开发指南

### 项目结构
```
web-monitor/
├── monitor/                 # 核心模块
│   ├── __init__.py
│   ├── config.py           # 配置管理
│   ├── database.py         # 数据库管理
│   ├── models.py           # 数据模型
│   ├── core.py             # 核心逻辑
│   ├── scheduler.py        # 任务调度
│   ├── fetcher.py          # 内容抓取
│   ├── detector.py         # 变化检测
│   ├── notifier.py         # 通知系统
│   ├── tasks.py            # Celery任务
│   ├── web.py              # Web界面
│   └── templates/          # 模板文件
├── config/                 # 配置文件
├── logs/                   # 日志文件
├── tests/                  # 测试用例
├── docs/                   # 文档
├── main.py                 # 主程序入口
├── requirements.txt        # 依赖包
├── docker-compose.yml      # Docker配置
├── Dockerfile             # Docker镜像
└── README.md              # 说明文档
```

### 运行测试
```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_fetcher.py

# 生成覆盖率报告
pytest --cov=monitor --cov-report=html
```

### 代码规范
```bash
# 格式化代码
black monitor/

# 检查代码风格
flake8 monitor/

# 类型检查
mypy monitor/
```

### 添加新功能

1. **添加新的检测算法**:
   - 在 `detector.py` 中实现新的检测器类
   - 继承 `BaseDetector` 基类
   - 实现 `detect_changes` 方法

2. **添加新的通知方式**:
   - 在 `notifier.py` 中实现新的通知器类
   - 继承 `BaseNotifier` 基类
   - 实现 `send_notification` 方法

3. **添加新的抓取方式**:
   - 在 `fetcher.py` 中实现新的抓取器类
   - 继承 `BaseFetcher` 基类
   - 实现 `fetch_content` 方法

## 🐛 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查PostgreSQL服务是否启动
   - 验证数据库连接参数
   - 确认数据库用户权限

2. **Redis连接失败**
   - 检查Redis服务是否启动
   - 验证Redis连接参数
   - 检查防火墙设置

3. **Selenium无法启动**
   - 安装Chrome浏览器
   - 更新ChromeDriver
   - 检查系统PATH环境变量

4. **任务执行失败**
   - 查看Celery工作进程日志
   - 检查网络连接
   - 验证目标网站可访问性

5. **内存使用过高**
   - 调整工作进程并发数
   - 清理历史数据
   - 优化检测算法

### 日志分析

```bash
# 查看应用日志
tail -f logs/app.log

# 查看错误日志
grep ERROR logs/app.log

# 查看任务执行情况
grep "Task completed" logs/celery.log
```

### 性能调优

1. **数据库调优**:
   ```sql
   -- 添加索引
   CREATE INDEX idx_website_url ON websites(url);
   CREATE INDEX idx_content_created_at ON webpage_contents(created_at);
   
   -- 清理历史数据
   DELETE FROM webpage_contents WHERE created_at < NOW() - INTERVAL '30 days';
   ```

2. **Redis调优**:
   ```redis
   # 设置内存淘汰策略
   CONFIG SET maxmemory-policy allkeys-lru
   
   # 启用压缩
   CONFIG SET rdbcompression yes
   ```

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📞 支持与反馈

- 问题报告: [GitHub Issues](https://github.com/your-repo/issues)
- 功能建议: [GitHub Discussions](https://github.com/your-repo/discussions)
- 邮件联系: support@example.com

## 🙏 致谢

感谢以下开源项目的支持：
- [Flask](https://flask.palletsprojects.com/) - Web框架
- [Celery](https://docs.celeryproject.org/) - 分布式任务队列
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM框架
- [Selenium](https://selenium-python.readthedocs.io/) - 浏览器自动化
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML解析
- [Bootstrap](https://getbootstrap.com/) - UI框架

---

**网页监控系统** - 让网页变化监控变得简单高效！