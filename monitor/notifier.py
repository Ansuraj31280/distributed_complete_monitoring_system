# 通知系统模块

import smtplib
import json
import requests
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from dataclasses import dataclass
from loguru import logger
from .config import config
from .database import db_manager, WebsiteModel, ChangeDetectionModel
from .detector import ChangeResult


@dataclass
class NotificationMessage:
    """通知消息"""
    title: str
    content: str
    website_id: int
    website_name: str
    website_url: str
    change_type: str
    change_score: float
    change_summary: str
    timestamp: datetime
    priority: str = 'normal'  # low, normal, high, urgent
    

class NotificationFilter:
    """通知过滤器"""
    
    def should_notify(self, website: WebsiteModel, change_result: ChangeResult) -> bool:
        """判断是否应该发送通知"""
        # 检查网站是否启用通知
        if not website.notification_enabled:
            return False
        
        # 检查变化分数阈值
        if change_result.change_score < website.notification_threshold:
            logger.debug(f"变化分数 {change_result.change_score} 低于阈值 {website.notification_threshold}，跳过通知")
            return False
        
        # 检查通知频率限制
        if self._is_rate_limited(website.id):
            logger.debug(f"网站 {website.id} 通知频率受限，跳过通知")
            return False
        
        # 检查静默时间
        if self._is_in_quiet_hours(website):
            logger.debug(f"网站 {website.id} 处于静默时间，跳过通知")
            return False
        
        return True
    
    def _is_rate_limited(self, website_id: int) -> bool:
        """检查通知频率限制"""
        try:
            # 获取最近的通知记录
            recent_notifications = db_manager.get_recent_notifications(
                website_id, 
                hours=24  # 默认24小时
            )
            return len(recent_notifications) >= 10  # 默认每小时最多10条通知
            
        except Exception as e:
            logger.error(f"检查通知频率限制失败: {str(e)}")
            return False
    
    def _is_in_quiet_hours(self, website: WebsiteModel) -> bool:
        """检查是否在静默时间内"""
        if not website.quiet_hours_enabled:
            return False
        
        try:
            now = datetime.now()
            current_hour = now.hour
            
            quiet_start = website.quiet_hours_start
            quiet_end = website.quiet_hours_end
            
            if quiet_start <= quiet_end:
                # 同一天内的时间段
                return quiet_start <= current_hour < quiet_end
            else:
                # 跨天的时间段
                return current_hour >= quiet_start or current_hour < quiet_end
                
        except Exception as e:
            logger.error(f"检查静默时间失败: {str(e)}")
            return False


class EmailNotifier:
    """邮件通知器"""
    
    def __init__(self, smtp_config=None):
        self.smtp_config = smtp_config or config.notification
    
    def send_notification(self, message: NotificationMessage, recipients: List[str]) -> bool:
        """发送邮件通知"""
        if not self.smtp_config.email_enabled or not recipients:
            return False
        
        try:
            # 创建邮件内容
            msg = MIMEMultipart('alternative')
            msg['Subject'] = Header(message.title, 'utf-8')
            msg['From'] = self.smtp_config.email_from_address
            msg['To'] = ', '.join(recipients)
            
            # 创建HTML和文本内容
            text_content = self._create_text_content(message)
            html_content = self._create_html_content(message)
            
            # 添加内容
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # 发送邮件
            with smtplib.SMTP(self.smtp_config.email_smtp_server, self.smtp_config.email_smtp_port) as server:
                # 默认使用TLS
                if True:
                    server.starttls()
                
                if self.smtp_config.email_username and self.smtp_config.email_password:
                    server.login(self.smtp_config.email_username, self.smtp_config.email_password)
                
                server.send_message(msg)
            
            logger.info(f"邮件通知发送成功 - 网站: {message.website_name}, 收件人: {len(recipients)}")
            return True
            
        except Exception as e:
            logger.error(f"邮件通知发送失败: {str(e)}")
            return False
    
    def _create_text_content(self, message: NotificationMessage) -> str:
        """创建文本内容"""
        return f"""
网页监控变化通知

网站名称: {message.website_name}
网站地址: {message.website_url}
变化类型: {message.change_type}
变化分数: {message.change_score:.3f}
检测时间: {message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

变化摘要:
{message.change_summary}

详细内容:
{message.content}

---
此邮件由网页监控系统自动发送
        """.strip()
    
    def _create_html_content(self, message: NotificationMessage) -> str:
        """创建HTML内容"""
        priority_colors = {
            'low': '#28a745',
            'normal': '#007bff',
            'high': '#fd7e14',
            'urgent': '#dc3545'
        }
        
        priority_color = priority_colors.get(message.priority, '#007bff')
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>网页监控变化通知</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: {priority_color}; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
        .content {{ background-color: #f8f9fa; padding: 20px; border: 1px solid #dee2e6; }}
        .footer {{ background-color: #e9ecef; padding: 10px; border-radius: 0 0 5px 5px; text-align: center; font-size: 12px; color: #6c757d; }}
        .info-table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        .info-table td {{ padding: 8px; border-bottom: 1px solid #dee2e6; }}
        .info-table td:first-child {{ font-weight: bold; width: 120px; }}
        .change-summary {{ background-color: white; padding: 15px; border-left: 4px solid {priority_color}; margin: 15px 0; }}
        .priority-badge {{ display: inline-block; padding: 4px 8px; border-radius: 3px; color: white; background-color: {priority_color}; font-size: 12px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🔔 网页监控变化通知</h2>
            <span class="priority-badge">{message.priority.upper()}</span>
        </div>
        
        <div class="content">
            <table class="info-table">
                <tr>
                    <td>网站名称:</td>
                    <td><strong>{message.website_name}</strong></td>
                </tr>
                <tr>
                    <td>网站地址:</td>
                    <td><a href="{message.website_url}" target="_blank">{message.website_url}</a></td>
                </tr>
                <tr>
                    <td>变化类型:</td>
                    <td>{message.change_type}</td>
                </tr>
                <tr>
                    <td>变化分数:</td>
                    <td>{message.change_score:.3f}</td>
                </tr>
                <tr>
                    <td>检测时间:</td>
                    <td>{message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td>
                </tr>
            </table>
            
            <div class="change-summary">
                <h4>📋 变化摘要</h4>
                <p>{message.change_summary}</p>
            </div>
            
            <div class="change-summary">
                <h4>📄 详细内容</h4>
                <pre style="white-space: pre-wrap; word-wrap: break-word;">{message.content}</pre>
            </div>
        </div>
        
        <div class="footer">
            此邮件由网页监控系统自动发送 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
        """.strip()


class WebhookNotifier:
    """Webhook通知器"""
    
    def __init__(self):
        self.webhook_config = config.notification
    
    def send_notification(self, message: NotificationMessage, webhook_urls: List[str]) -> bool:
        """发送Webhook通知"""
        if not self.webhook_config.webhook_enabled or not webhook_urls:
            return False
        
        success_count = 0
        
        for url in webhook_urls:
            try:
                payload = self._create_webhook_payload(message)
                
                response = requests.post(
                    url,
                    json=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': 'WebMonitor/1.0'
                    },
                    timeout=self.webhook_config.timeout
                )
                
                response.raise_for_status()
                success_count += 1
                
                logger.info(f"Webhook通知发送成功 - URL: {url}")
                
            except Exception as e:
                logger.error(f"Webhook通知发送失败 - URL: {url}, 错误: {str(e)}")
        
        return success_count > 0
    
    def _create_webhook_payload(self, message: NotificationMessage) -> Dict[str, Any]:
        """创建Webhook载荷"""
        return {
            'event': 'website_change_detected',
            'timestamp': message.timestamp.isoformat(),
            'website': {
                'id': message.website_id,
                'name': message.website_name,
                'url': message.website_url
            },
            'change': {
                'type': message.change_type,
                'score': message.change_score,
                'summary': message.change_summary,
                'priority': message.priority
            },
            'notification': {
                'title': message.title,
                'content': message.content
            }
        }


class DingTalkNotifier:
    """钉钉通知器"""
    
    def __init__(self):
        self.dingtalk_config = config.notification
    
    def send_notification(self, message: NotificationMessage, webhook_urls: List[str]) -> bool:
        """发送钉钉通知"""
        if not self.dingtalk_config.dingtalk_enabled or not webhook_urls:
            return False
        
        success_count = 0
        
        for url in webhook_urls:
            try:
                payload = self._create_dingtalk_payload(message)
                
                response = requests.post(
                    url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                response.raise_for_status()
                result = response.json()
                
                if result.get('errcode') == 0:
                    success_count += 1
                    logger.info(f"钉钉通知发送成功 - URL: {url}")
                else:
                    logger.error(f"钉钉通知发送失败 - URL: {url}, 错误: {result.get('errmsg')}")
                
            except Exception as e:
                logger.error(f"钉钉通知发送失败 - URL: {url}, 错误: {str(e)}")
        
        return success_count > 0
    
    def _create_dingtalk_payload(self, message: NotificationMessage) -> Dict[str, Any]:
        """创建钉钉载荷"""
        priority_emojis = {
            'low': '🟢',
            'normal': '🔵',
            'high': '🟠',
            'urgent': '🔴'
        }
        
        emoji = priority_emojis.get(message.priority, '🔵')
        
        markdown_content = f"""
# {emoji} 网页监控变化通知

**网站名称:** {message.website_name}

**网站地址:** [{message.website_url}]({message.website_url})

**变化类型:** {message.change_type}

**变化分数:** {message.change_score:.3f}

**检测时间:** {message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

**变化摘要:**
```
{message.change_summary}
```

**优先级:** {message.priority.upper()}
        """.strip()
        
        return {
            'msgtype': 'markdown',
            'markdown': {
                'title': message.title,
                'text': markdown_content
            }
        }


class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        self.filter = NotificationFilter()
        self.email_notifier = EmailNotifier()
        self.webhook_notifier = WebhookNotifier()
        self.dingtalk_notifier = DingTalkNotifier()
    
    def send_change_notification(self, website_id: int, change_result: ChangeResult) -> bool:
        """发送变化通知"""
        try:
            # 获取网站配置
            website = db_manager.get_website(website_id)
            if not website:
                logger.error(f"网站不存在 - ID: {website_id}")
                return False
            
            # 检查是否应该发送通知
            if not self.filter.should_notify(website, change_result):
                return False
            
            # 创建通知消息
            message = self._create_notification_message(website, change_result)
            
            # 确定优先级
            message.priority = self._determine_priority(change_result.change_score)
            
            # 发送通知
            success = False
            
            # 邮件通知
            if website.email_notifications and website.notification_emails:
                email_success = self.email_notifier.send_notification(
                    message, 
                    website.notification_emails
                )
                success = success or email_success
            
            # Webhook通知
            if website.webhook_notifications and website.webhook_urls:
                webhook_success = self.webhook_notifier.send_notification(
                    message,
                    website.webhook_urls
                )
                success = success or webhook_success
            
            # 钉钉通知
            if website.dingtalk_notifications and website.dingtalk_webhooks:
                dingtalk_success = self.dingtalk_notifier.send_notification(
                    message,
                    website.dingtalk_webhooks
                )
                success = success or dingtalk_success
            
            # 记录通知历史
            if success:
                self._save_notification_history(website_id, message, change_result)
                logger.info(f"变化通知发送成功 - 网站: {website.name}")
            
            return success
            
        except Exception as e:
            logger.error(f"发送变化通知异常 - 网站ID: {website_id}, 错误: {str(e)}")
            return False
    
    def _create_notification_message(self, website: WebsiteModel, change_result: ChangeResult) -> NotificationMessage:
        """创建通知消息"""
        title = f"🔔 {website.name} - 检测到内容变化"
        
        content = f"""
变化详情:
{change_result.diff_summary}

变化分数: {change_result.change_score:.3f}
变化类型: {change_result.change_type}

检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
        
        return NotificationMessage(
            title=title,
            content=content,
            website_id=website.id,
            website_name=website.name,
            website_url=website.url,
            change_type=change_result.change_type,
            change_score=change_result.change_score,
            change_summary=change_result.diff_summary,
            timestamp=datetime.now(timezone.utc)
        )
    
    def _determine_priority(self, change_score: float) -> str:
        """确定通知优先级"""
        if change_score >= 0.8:
            return 'urgent'
        elif change_score >= 0.6:
            return 'high'
        elif change_score >= 0.3:
            return 'normal'
        else:
            return 'low'
    
    def _save_notification_history(self, website_id: int, message: NotificationMessage, change_result: ChangeResult):
        """保存通知历史"""
        try:
            notification_data = {
                'website_id': website_id,
                'notification_type': 'change_detection',
                'title': message.title,
                'content': message.content,
                'priority': message.priority,
                'change_score': change_result.change_score,
                'sent_at': message.timestamp
            }
            
            db_manager.save_notification_history(notification_data)
            
        except Exception as e:
            logger.error(f"保存通知历史失败: {str(e)}")
    
    def send_system_notification(self, title: str, content: str, priority: str = 'normal') -> bool:
        """发送系统通知"""
        try:
            message = NotificationMessage(
                title=title,
                content=content,
                website_id=0,
                website_name='系统',
                website_url='',
                change_type='system',
                change_score=0.0,
                change_summary=content,
                timestamp=datetime.now(timezone.utc),
                priority=priority
            )
            
            # 发送到系统管理员邮箱
            if config.notification.email_enabled:
                # 使用默认管理员邮箱
                admin_emails = ['admin@example.com']  # 可以从配置中获取
                self.email_notifier.send_notification(
                    message,
                    admin_emails
                )
            
            return False
            
        except Exception as e:
            logger.error(f"发送系统通知异常: {str(e)}")
            return False
    
    async def send_batch_notifications(self, notifications: List[Tuple[int, ChangeResult]]) -> Dict[str, int]:
        """批量发送通知"""
        results = {
            'success': 0,
            'failed': 0,
            'skipped': 0
        }
        
        tasks = []
        for website_id, change_result in notifications:
            task = asyncio.create_task(self._async_send_notification(website_id, change_result))
            tasks.append(task)
        
        notification_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in notification_results:
            if isinstance(result, Exception):
                results['failed'] += 1
            elif result is True:
                results['success'] += 1
            elif result is False:
                results['skipped'] += 1
            else:
                results['failed'] += 1
        
        return results
    
    async def _async_send_notification(self, website_id: int, change_result: ChangeResult) -> bool:
        """异步发送通知"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self.send_change_notification, 
            website_id, 
            change_result
        )


# 全局通知管理器实例
notification_manager = NotificationManager()