# 分布式网页监控系统

> ⚠️ **AI生成项目声明**: 本项目代码完全由人工智能自主生成，仅作为技术演示和学习参考使用。请在生产环境中谨慎使用，并进行充分的测试和安全评估。

一个功能强大的分布式网页内容监控系统，支持海量网页并发监控、智能变化检测和多种通知方式。本项目展示了现代Python Web应用的完整架构设计，包括分布式任务处理、数据持久化、实时通知等核心功能。

## 🚀 核心特性

### 🔍 智能监控
- **海量并发监控**: 基于Celery分布式任务队列，支持数万个网页同时监控
- **多维度检测**: 支持文本内容、DOM结构、图片等多种变化检测算法
- **智能过滤**: 基于机器学习的语义分析，过滤无意义的页面变化
- **灵活配置**: 支持CSS选择器、XPath等精确定位监控区域

### 🛡️ 反爬虫机制
- **User-Agent轮换**: 内置多种浏览器标识，模拟真实用户访问
- **代理支持**: 支持HTTP/HTTPS代理池，分散请求来源
- **随机延迟**: 智能延迟策略，避免频繁请求被检测
- **Session管理**: 支持Cookie和Session保持，应对登录验证

### 📊 数据管理
- **双重存储**: PostgreSQL持久化存储 + Redis高速缓存
- **数据压缩**: 智能内容压缩，节省存储空间
- **历史追踪**: 完整的变化历史记录和版本对比
- **数据导出**: 支持多种格式的数据导出功能

### 🔔 实时通知
- **多渠道通知**: 邮件、钉钉、Webhook等多种通知方式
- **智能聚合**: 防止通知轰炸，支持通知频率限制
- **模板定制**: 可自定义通知内容模板和格式
- **条件触发**: 支持基于变化程度的条件通知

### 🌐 Web管理界面
- **现代化UI**: 基于Bootstrap的响应式设计
- **实时监控**: WebSocket实时更新监控状态
- **可视化配置**: 图形化的网站配置和管理界面
- **统计分析**: 丰富的图表和统计信息展示

## 📋 技术栈

### 后端技术
- **Python 3.8+**: 主要开发语言
- **Flask**: Web框架，提供API和管理界面
- **Celery**: 分布式任务队列，处理异步监控任务
- **SQLAlchemy**: ORM框架，数据库操作抽象层
- **PostgreSQL**: 主数据库，存储网站配置和监控数据
- **Redis**: 缓存和消息队列，提升系统性能

### 前端技术
- **Bootstrap 5**: UI框架，响应式设计
- **jQuery**: JavaScript库，DOM操作和AJAX
- **Chart.js**: 图表库，数据可视化
- **WebSocket**: 实时通信，状态更新

### 爬虫技术
- **Requests**: HTTP客户端，处理常规网页请求
- **Selenium**: 浏览器自动化，处理JavaScript渲染页面
- **BeautifulSoup**: HTML解析，内容提取和分析
- **lxml**: XML/HTML解析器，高性能解析

## 🛠️ 快速开始

### 环境要求
- Python 3.8 或更高版本
- PostgreSQL 12 或更高版本
- Redis 6 或更高版本
- Chrome/Chromium 浏览器（用于Selenium）

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd distributed_complete_monitoring_system
```

2. **创建虚拟环境**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库和Redis连接信息
```

5. **初始化数据库**
```bash
python main.py init-db
```

6. **检查系统依赖**
```bash
python main.py check
```

### 启动系统

#### 开发环境（单进程模式）
```bash
python main.py monitor
```

#### 生产环境（多进程模式）
```bash
# 终端1: 启动Web服务
python main.py web --host 0.0.0.0 --port 5000

# 终端2: 启动工作进程
python main.py worker --concurrency 4

# 终端3: 启动定时调度器
python main.py beat
```

#### Docker部署
```bash
# 构建并启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

## 📖 使用指南

### 访问Web界面
启动系统后，在浏览器中访问 `http://localhost:5000`

默认管理员账户：
- 用户名: `admin`
- 密码: `admin123`

### 添加监控网站

1. 登录管理界面
2. 点击「添加网站」按钮
3. 填写网站基本信息：
   - **网站名称**: 便于识别的显示名称
   - **监控URL**: 要监控的完整网页地址
   - **检查间隔**: 监控频率（分钟为单位）
   - **检测算法**: 选择合适的变化检测方式

4. 高级配置（可选）：
   - **CSS选择器**: 指定监控的页面元素
   - **请求头**: 自定义HTTP请求头
   - **Cookies**: 设置访问所需的Cookie
   - **代理设置**: 配置代理服务器

### 检测算法说明

- **哈希检测**: 计算页面内容MD5值，快速检测整体变化
- **文本差异**: 逐行对比文本内容，显示具体变化位置
- **DOM结构**: 分析HTML结构变化，适用于动态网页
- **语义分析**: 基于NLP技术，识别内容语义变化

### 通知配置

#### 邮件通知
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
```

#### 钉钉通知
```env
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
DINGTALK_SECRET=your-secret-key
```

#### Webhook通知
```env
WEBHOOK_URL=https://your-webhook-endpoint.com/notify
WEBHOOK_SECRET=your-webhook-secret
```

## 🔧 配置详解

### 系统配置文件
主配置文件位于 `config/config.yaml`，包含以下主要配置项：

```yaml
# 数据库配置
database:
  postgresql:
    host: localhost
    port: 5432
    database: monitor
    username: monitor
    password: monitor123
  redis:
    host: localhost
    port: 6379
    db: 0

# 任务队列配置
celery:
  broker_url: redis://localhost:6379/1
  result_backend: redis://localhost:6379/2
  worker_concurrency: 4

# 监控配置
monitoring:
  max_concurrent_requests: 10
  request_timeout: 30
  retry_attempts: 3
  user_agent_rotation: true

# 通知配置
notification:
  rate_limit:
    cooldown_minutes: 30
    max_per_hour: 10
```

### 环境变量配置
系统支持通过环境变量覆盖配置文件设置：

```env
# 数据库连接
DATABASE_URL=postgresql://user:pass@localhost:5432/monitor
REDIS_URL=redis://localhost:6379/0

# 安全配置
SECRET_KEY=your-secret-key-change-in-production
JWT_SECRET_KEY=your-jwt-secret-change-in-production

# 应用配置
FLASK_ENV=production
FLASK_DEBUG=false
CELERY_WORKER_CONCURRENCY=8
```

## 📊 API文档

### 认证
所有API请求需要在Header中包含JWT令牌：
```http
Authorization: Bearer <your-jwt-token>
```

### 网站管理API

#### 获取网站列表
```http
GET /api/websites
Response: {
  "websites": [
    {
      "id": 1,
      "name": "示例网站",
      "url": "https://example.com",
      "status": "active",
      "last_check": "2024-01-15T10:30:00Z",
      "check_interval": 60
    }
  ]
}
```

#### 添加监控网站
```http
POST /api/websites
Content-Type: application/json

{
  "name": "新网站",
  "url": "https://newsite.com",
  "check_interval": 30,
  "detection_algorithm": "hash",
  "css_selector": ".content",
  "notification_emails": ["admin@example.com"]
}
```

#### 手动触发检查
```http
POST /api/websites/{id}/check
Response: {
  "task_id": "abc123-def456-789",
  "status": "pending"
}
```

### 监控数据API

#### 获取变化历史
```http
GET /api/websites/{id}/changes?limit=50&offset=0
Response: {
  "changes": [
    {
      "id": 1,
      "detected_at": "2024-01-15T10:30:00Z",
      "change_type": "content_modified",
      "similarity_score": 0.85,
      "diff_summary": "标题从'旧标题'变更为'新标题'"
    }
  ],
  "total": 150
}
```

#### 获取系统统计
```http
GET /api/system/stats
Response: {
  "total_websites": 100,
  "active_websites": 95,
  "total_checks_today": 2400,
  "changes_detected_today": 15,
  "system_uptime": "5 days, 12:30:45",
  "queue_status": {
    "pending_tasks": 5,
    "active_workers": 4
  }
}
```

## 🏗️ 项目架构

### 目录结构
```
distributed_complete_monitoring_system/
├── monitor/                    # 核心应用模块
│   ├── __init__.py            # 模块初始化
│   ├── config.py              # 配置管理
│   ├── database.py            # 数据库连接和模型
│   ├── models.py              # 数据模型定义
│   ├── core.py                # 核心业务逻辑
│   ├── scheduler.py           # 任务调度器
│   ├── fetcher.py             # 网页内容抓取
│   ├── detector.py            # 变化检测算法
│   ├── notifier.py            # 通知系统
│   ├── tasks.py               # Celery异步任务
│   ├── web.py                 # Flask Web应用
│   └── templates/             # HTML模板文件
│       ├── base.html          # 基础模板
│       ├── dashboard.html     # 仪表板页面
│       ├── websites.html      # 网站列表页面
│       └── settings.html      # 设置页面
├── config/                    # 配置文件目录
│   └── config.yaml           # 主配置文件
├── logs/                      # 日志文件目录
├── main.py                    # 应用程序入口
├── requirements.txt           # Python依赖包
├── docker-compose.yml         # Docker编排配置
├── Dockerfile                 # Docker镜像构建
├── .env.example              # 环境变量示例
├── .gitignore                # Git忽略文件
└── README.md                 # 项目说明文档
```

### 系统架构图
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │    │   Mobile App    │    │   API Client    │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────┴─────────────┐
                    │      Flask Web App       │
                    │   (API + Web Interface)  │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │      Redis Broker        │
                    │   (Task Queue + Cache)   │
                    └─────────────┬─────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
┌───────┴────────┐    ┌──────────┴──────────┐    ┌─────────┴────────┐
│ Celery Worker  │    │  Celery Worker      │    │ Celery Beat      │
│   (Fetcher)    │    │   (Detector)        │    │  (Scheduler)     │
└───────┬────────┘    └──────────┬──────────┘    └─────────┬────────┘
        │                        │                         │
        └────────────────────────┼─────────────────────────┘
                                 │
                    ┌─────────────┴─────────────┐
                    │     PostgreSQL DB        │
                    │  (Persistent Storage)    │
                    └───────────────────────────┘
```

## 🧪 开发指南

### 开发环境设置

1. **安装开发依赖**
```bash
pip install -r requirements-dev.txt
```

2. **配置开发环境**
```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
```

3. **运行开发服务器**
```bash
python main.py web --debug
```

### 代码规范

项目遵循PEP 8代码规范，使用以下工具进行代码质量控制：

```bash
# 代码格式化
black monitor/

# 代码风格检查
flake8 monitor/

# 类型检查
mypy monitor/

# 安全检查
bandit -r monitor/
```

### 测试

```bash
# 运行单元测试
pytest tests/

# 生成覆盖率报告
pytest --cov=monitor --cov-report=html

# 运行集成测试
pytest tests/integration/
```

### 扩展开发

#### 添加新的检测算法

1. 在 `monitor/detector.py` 中创建新的检测器类：

```python
class CustomDetector(BaseDetector):
    """自定义检测算法"""
    
    def detect_changes(self, old_content: str, new_content: str) -> DetectionResult:
        """实现自定义检测逻辑"""
        # 你的检测算法实现
        pass
```

2. 在配置中注册新算法：

```yaml
detection_algorithms:
  custom:
    class: monitor.detector.CustomDetector
    enabled: true
```

#### 添加新的通知方式

1. 在 `monitor/notifier.py` 中创建新的通知器类：

```python
class CustomNotifier(BaseNotifier):
    """自定义通知方式"""
    
    def send_notification(self, message: NotificationMessage) -> bool:
        """发送通知"""
        # 你的通知发送逻辑
        pass
```

2. 在配置中启用新通知方式：

```yaml
notifiers:
  custom:
    class: monitor.notifier.CustomNotifier
    enabled: true
    config:
      api_key: your-api-key
```

## 🐛 故障排除

### 常见问题

#### 1. 数据库连接失败
**症状**: 启动时报告数据库连接错误

**解决方案**:
- 检查PostgreSQL服务是否运行
- 验证数据库连接参数
- 确认数据库用户权限
- 检查防火墙设置

```bash
# 测试数据库连接
psql -h localhost -U monitor -d monitor

# 检查PostgreSQL状态
sudo systemctl status postgresql
```

#### 2. Redis连接失败
**症状**: Celery任务无法执行

**解决方案**:
- 检查Redis服务状态
- 验证Redis连接参数
- 检查Redis内存使用情况

```bash
# 测试Redis连接
redis-cli ping

# 检查Redis状态
sudo systemctl status redis
```

#### 3. Selenium无法启动
**症状**: 使用Selenium抓取时报错

**解决方案**:
- 安装Chrome浏览器
- 更新ChromeDriver版本
- 检查系统PATH环境变量
- 确认Chrome和ChromeDriver版本兼容

```bash
# 检查Chrome版本
google-chrome --version

# 检查ChromeDriver版本
chromedriver --version
```

#### 4. 内存使用过高
**症状**: 系统内存占用持续增长

**解决方案**:
- 调整Celery工作进程数量
- 清理历史监控数据
- 优化检测算法参数
- 启用Redis内存淘汰策略

```bash
# 监控内存使用
top -p $(pgrep -f celery)

# 清理历史数据
python main.py cleanup --days 30
```

### 性能优化

#### 数据库优化

```sql
-- 添加必要索引
CREATE INDEX CONCURRENTLY idx_websites_url ON websites(url);
CREATE INDEX CONCURRENTLY idx_contents_created_at ON webpage_contents(created_at);
CREATE INDEX CONCURRENTLY idx_changes_website_id ON change_detections(website_id);

-- 定期清理历史数据
DELETE FROM webpage_contents 
WHERE created_at < NOW() - INTERVAL '90 days';

-- 分析表统计信息
ANALYZE websites;
ANALYZE webpage_contents;
```

#### Redis优化

```redis
# 设置内存淘汰策略
CONFIG SET maxmemory-policy allkeys-lru

# 启用压缩
CONFIG SET rdbcompression yes

# 调整持久化策略
CONFIG SET save "900 1 300 10 60 10000"
```

#### 应用优化

```python
# 调整Celery配置
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# 启用连接池
DATABASE_POOL_SIZE = 20
DATABASE_MAX_OVERFLOW = 30
REDIS_CONNECTION_POOL_MAX_CONNECTIONS = 50
```

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 贡献规范

- 遵循现有代码风格
- 添加适当的测试用例
- 更新相关文档
- 确保所有测试通过

## 📞 支持与反馈

- **问题报告**: [GitHub Issues](https://github.com/your-repo/issues)
- **功能建议**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **安全问题**: security@example.com

## 🙏 致谢

感谢以下开源项目的支持：

- [Flask](https://flask.palletsprojects.com/) - 轻量级Web框架
- [Celery](https://docs.celeryproject.org/) - 分布式任务队列
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL工具包
- [Selenium](https://selenium-python.readthedocs.io/) - Web浏览器自动化
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML/XML解析库
- [Bootstrap](https://getbootstrap.com/) - 前端UI框架
- [Redis](https://redis.io/) - 内存数据结构存储
- [PostgreSQL](https://www.postgresql.org/) - 开源关系型数据库

---

**分布式网页监控系统** - 让网页变化监控变得智能、高效、可靠！

> 本项目完全由AI生成，展示了现代软件工程的最佳实践。适合用于学习分布式系统架构、异步任务处理、Web开发等技术领域。