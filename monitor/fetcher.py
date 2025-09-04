# 网页抓取模块

import asyncio
import aiohttp
import requests
import hashlib
import random
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from loguru import logger
from .config import config
from .database import db_manager, WebsiteModel, WebpageContentModel


class UserAgentRotator:
    """用户代理轮换器"""
    
    def __init__(self):
        self.user_agents = config.fetcher.user_agents
        self.current_index = 0
    
    def get_random_user_agent(self) -> str:
        """获取随机用户代理"""
        return random.choice(self.user_agents)
    
    def get_next_user_agent(self) -> str:
        """获取下一个用户代理（轮换）"""
        user_agent = self.user_agents[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.user_agents)
        return user_agent


class ProxyManager:
    """代理管理器"""
    
    def __init__(self):
        self.proxies = config.fetcher.proxies_pool if config.fetcher.proxies_enabled else []
        self.current_index = 0
        self.failed_proxies = set()
    
    def get_proxy(self) -> Optional[Dict[str, str]]:
        """获取可用代理"""
        if not self.proxies:
            return None
        
        available_proxies = [p for p in self.proxies if p not in self.failed_proxies]
        if not available_proxies:
            # 重置失败代理列表
            self.failed_proxies.clear()
            available_proxies = self.proxies
        
        proxy = random.choice(available_proxies)
        return {
            'http': proxy,
            'https': proxy
        }
    
    def mark_proxy_failed(self, proxy: str):
        """标记代理失败"""
        self.failed_proxies.add(proxy)


class AntiDetectionMixin:
    """反检测混入类"""
    
    def add_random_delay(self, min_delay: float = 1.0, max_delay: float = 3.0):
        """添加随机延迟"""
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def get_random_headers(self, user_agent: str) -> Dict[str, str]:
        """获取随机请求头"""
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': random.choice([
                'zh-CN,zh;q=0.9,en;q=0.8',
                'en-US,en;q=0.9',
                'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2'
            ]),
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': random.choice(['no-cache', 'max-age=0'])
        }
        
        # 随机添加一些可选头
        if random.random() < 0.3:
            headers['Referer'] = 'https://www.google.com/'
        
        if random.random() < 0.2:
            headers['X-Forwarded-For'] = f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
        
        return headers


class RequestsFetcher(AntiDetectionMixin):
    """基于Requests的网页抓取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.user_agent_rotator = UserAgentRotator()
        self.proxy_manager = ProxyManager()
        
        # 设置会话配置
        self.session.max_redirects = 10
        
        # 设置连接池
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=20,
            max_retries=0
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def fetch_content(self, url: str, website_config: WebsiteModel) -> Dict[str, Any]:
        """抓取网页内容（别名方法）"""
        return self.fetch(url, website_config)
    
    def fetch(self, url: str, website_config: WebsiteModel) -> Dict[str, Any]:
        """抓取网页内容"""
        start_time = time.time()
        
        try:
            # 准备请求参数
            user_agent = website_config.user_agent or self.user_agent_rotator.get_random_user_agent()
            headers = self.get_random_headers(user_agent)
            
            # 合并自定义请求头
            if website_config.headers:
                headers.update(website_config.headers)
            
            # 设置代理
            proxies = None
            if website_config.proxy:
                proxies = {
                    'http': website_config.proxy,
                    'https': website_config.proxy
                }
            elif config.fetcher.proxies_enabled:
                proxies = self.proxy_manager.get_proxy()
            
            # 设置Cookie
            if website_config.cookies:
                self.session.cookies.update(website_config.cookies)
            
            # 添加随机延迟
            self.add_random_delay()
            
            # 发送请求
            response = self.session.get(
                url,
                headers=headers,
                proxies=proxies,
                timeout=config.fetcher.timeout,
                allow_redirects=True,
                verify=True
            )
            
            response.raise_for_status()
            
            # 计算响应时间
            response_time = time.time() - start_time
            
            # 解析内容
            content_data = self._parse_content(response, website_config)
            
            return {
                'success': True,
                'status_code': response.status_code,
                'response_time': response_time,
                'content_length': len(response.text),
                'raw_content': response.text,
                'extracted_content': content_data['extracted_content'],
                'content_hash': content_data['content_hash'],
                'final_url': response.url
            }
            
        except requests.exceptions.ProxyError as e:
            if proxies:
                proxy_url = proxies.get('http') or proxies.get('https')
                self.proxy_manager.mark_proxy_failed(proxy_url)
            
            logger.warning(f"代理错误: {str(e)}")
            return {
                'success': False,
                'error': f"代理错误: {str(e)}",
                'status_code': None,
                'response_time': time.time() - start_time
            }
            
        except requests.exceptions.Timeout as e:
            logger.warning(f"请求超时: {str(e)}")
            return {
                'success': False,
                'error': f"请求超时: {str(e)}",
                'status_code': None,
                'response_time': time.time() - start_time
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"请求异常: {str(e)}")
            return {
                'success': False,
                'error': f"请求异常: {str(e)}",
                'status_code': getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
                'response_time': time.time() - start_time
            }
        
        except Exception as e:
            logger.error(f"未知错误: {str(e)}")
            return {
                'success': False,
                'error': f"未知错误: {str(e)}",
                'status_code': None,
                'response_time': time.time() - start_time
            }
    
    def _parse_content(self, response: requests.Response, website_config: WebsiteModel) -> Dict[str, Any]:
        """解析网页内容"""
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取目标内容
            extracted_content = response.text
            
            if website_config.selector:
                # 使用CSS选择器
                elements = soup.select(website_config.selector)
                if elements:
                    extracted_content = '\n'.join([elem.get_text(strip=True) for elem in elements])
            
            elif website_config.xpath:
                # XPath功能暂时不可用（需要lxml），使用原始内容
                logger.warning("XPath选择器需要lxml库，当前使用原始内容")
                extracted_content = soup.get_text(strip=True)
            
            # 计算内容哈希
            content_hash = hashlib.sha256(extracted_content.encode('utf-8')).hexdigest()
            
            return {
                'extracted_content': extracted_content,
                'content_hash': content_hash
            }
            
        except Exception as e:
            logger.error(f"内容解析失败: {str(e)}")
            # 使用原始内容作为备选
            content_hash = hashlib.sha256(response.text.encode('utf-8')).hexdigest()
            return {
                'extracted_content': response.text,
                'content_hash': content_hash
            }


class SeleniumFetcher(AntiDetectionMixin):
    """基于Selenium的网页抓取器"""
    
    def __init__(self):
        self.user_agent_rotator = UserAgentRotator()
        self.proxy_manager = ProxyManager()
    
    def _create_driver(self, website_config: WebsiteModel) -> webdriver.Chrome:
        """创建WebDriver实例"""
        options = Options()
        
        # 基础配置
        if config.fetcher.selenium_headless:
            options.add_argument('--headless')
        
        options.add_argument(f'--window-size={config.fetcher.selenium_window_size}')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-images')
        options.add_argument('--disable-javascript')
        
        # 反检测配置
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 设置用户代理
        user_agent = website_config.user_agent or self.user_agent_rotator.get_random_user_agent()
        options.add_argument(f'--user-agent={user_agent}')
        
        # 设置代理
        if website_config.proxy:
            options.add_argument(f'--proxy-server={website_config.proxy}')
        elif config.fetcher.proxies_enabled:
            proxy = self.proxy_manager.get_proxy()
            if proxy:
                proxy_url = proxy.get('http', '').replace('http://', '')
                options.add_argument(f'--proxy-server={proxy_url}')
        
        # 创建驱动
        driver = webdriver.Chrome(
            executable_path=config.fetcher.selenium_driver_path,
            options=options
        )
        
        # 设置页面加载超时
        driver.set_page_load_timeout(config.fetcher.selenium_page_load_timeout)
        
        # 执行反检测脚本
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    
    def fetch(self, url: str, website_config: WebsiteModel) -> Dict[str, Any]:
        """使用Selenium抓取网页内容"""
        start_time = time.time()
        driver = None
        
        try:
            # 创建驱动
            driver = self._create_driver(website_config)
            
            # 设置Cookie
            if website_config.cookies:
                driver.get(url)  # 先访问页面以设置域
                for name, value in website_config.cookies.items():
                    driver.add_cookie({'name': name, 'value': value})
            
            # 添加随机延迟
            self.add_random_delay()
            
            # 访问页面
            driver.get(url)
            
            # 等待页面加载
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 模拟人类行为
            self._simulate_human_behavior(driver)
            
            # 获取页面内容
            page_source = driver.page_source
            final_url = driver.current_url
            
            # 计算响应时间
            response_time = time.time() - start_time
            
            # 解析内容
            content_data = self._parse_content(page_source, website_config)
            
            return {
                'success': True,
                'status_code': 200,  # Selenium无法直接获取状态码
                'response_time': response_time,
                'content_length': len(page_source),
                'raw_content': page_source,
                'extracted_content': content_data['extracted_content'],
                'content_hash': content_data['content_hash'],
                'final_url': final_url
            }
            
        except TimeoutException as e:
            logger.warning(f"Selenium页面加载超时: {str(e)}")
            return {
                'success': False,
                'error': f"页面加载超时: {str(e)}",
                'status_code': None,
                'response_time': time.time() - start_time
            }
            
        except WebDriverException as e:
            logger.error(f"Selenium WebDriver异常: {str(e)}")
            return {
                'success': False,
                'error': f"WebDriver异常: {str(e)}",
                'status_code': None,
                'response_time': time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Selenium未知错误: {str(e)}")
            return {
                'success': False,
                'error': f"未知错误: {str(e)}",
                'status_code': None,
                'response_time': time.time() - start_time
            }
            
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logger.warning(f"关闭WebDriver失败: {str(e)}")
    
    def _simulate_human_behavior(self, driver: webdriver.Chrome):
        """模拟人类行为"""
        try:
            # 随机滚动页面
            if random.random() < 0.5:
                scroll_height = driver.execute_script("return document.body.scrollHeight")
                scroll_position = random.randint(0, scroll_height // 2)
                driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                time.sleep(random.uniform(0.5, 1.5))
            
            # 随机移动鼠标
            if random.random() < 0.3:
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(driver)
                actions.move_by_offset(random.randint(10, 100), random.randint(10, 100))
                actions.perform()
                time.sleep(random.uniform(0.2, 0.8))
                
        except Exception as e:
            logger.debug(f"模拟人类行为失败: {str(e)}")
    
    def _parse_content(self, page_source: str, website_config: WebsiteModel) -> Dict[str, Any]:
        """解析网页内容"""
        try:
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # 提取目标内容
            extracted_content = page_source
            
            if website_config.selector:
                # 使用CSS选择器
                elements = soup.select(website_config.selector)
                if elements:
                    extracted_content = '\n'.join([elem.get_text(strip=True) for elem in elements])
            
            elif website_config.xpath:
                # XPath功能暂时不可用（需要lxml），使用原始内容
                logger.warning("XPath选择器需要lxml库，当前使用原始内容")
                extracted_content = soup.get_text(strip=True)
            
            # 计算内容哈希
            content_hash = hashlib.sha256(extracted_content.encode('utf-8')).hexdigest()
            
            return {
                'extracted_content': extracted_content,
                'content_hash': content_hash
            }
            
        except Exception as e:
            logger.error(f"Selenium内容解析失败: {str(e)}")
            # 使用原始内容作为备选
            content_hash = hashlib.sha256(page_source.encode('utf-8')).hexdigest()
            return {
                'extracted_content': page_source,
                'content_hash': content_hash
            }


class WebpageFetcher:
    """网页抓取器主类"""
    
    def __init__(self):
        self.requests_fetcher = RequestsFetcher()
        self.selenium_fetcher = SeleniumFetcher()
    
    def fetch_website(self, website_id: int) -> Dict[str, Any]:
        """抓取指定网站"""
        try:
            # 获取网站配置
            website = db_manager.get_website(website_id)
            if not website:
                raise ValueError(f"网站不存在 - ID: {website_id}")
            
            if not website.enabled:
                raise ValueError(f"网站已禁用 - ID: {website_id}")
            
            logger.info(f"开始抓取网站 - ID: {website_id}, URL: {website.url}")
            
            # 选择抓取器
            if website.use_selenium:
                result = self._fetch_with_retry(self.selenium_fetcher, website)
            else:
                result = self._fetch_with_retry(self.requests_fetcher, website)
            
            # 保存抓取结果
            if result['success']:
                content_id = self._save_content(website_id, result)
                result['content_id'] = content_id
                
                # 更新网站检查时间
                db_manager.update_website_check_time(website_id)
                
                logger.info(f"网站抓取成功 - ID: {website_id}, 内容ID: {content_id}")
            else:
                # 保存错误信息
                self._save_error(website_id, result)
                logger.warning(f"网站抓取失败 - ID: {website_id}, 错误: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"抓取网站异常 - ID: {website_id}, 错误: {str(e)}")
            return {
                'success': False,
                'error': f"抓取异常: {str(e)}",
                'website_id': website_id
            }
    
    def _fetch_with_retry(self, fetcher, website: WebsiteModel) -> Dict[str, Any]:
        """带重试的抓取"""
        last_error = None
        
        for attempt in range(config.fetcher.max_retries + 1):
            try:
                if attempt > 0:
                    # 重试前等待
                    time.sleep(config.fetcher.retry_delay * attempt)
                    logger.info(f"重试抓取 - 第{attempt}次, URL: {website.url}")
                
                result = fetcher.fetch(website.url, website)
                
                if result['success']:
                    return result
                else:
                    last_error = result.get('error', '未知错误')
                    
                    # 某些错误不需要重试
                    if 'timeout' not in last_error.lower() and 'connection' not in last_error.lower():
                        break
                        
            except Exception as e:
                last_error = str(e)
                logger.warning(f"抓取尝试失败 - 第{attempt}次, 错误: {last_error}")
        
        return {
            'success': False,
            'error': f"重试{config.fetcher.max_retries}次后仍然失败: {last_error}",
            'website_id': website.id
        }
    
    def _save_content(self, website_id: int, result: Dict[str, Any]) -> int:
        """保存抓取的内容"""
        content_data = {
            'website_id': website_id,
            'content_hash': result['content_hash'],
            'raw_content': result['raw_content'],
            'extracted_content': result['extracted_content'],
            'content_length': result['content_length'],
            'response_time': result['response_time'],
            'status_code': result['status_code']
        }
        
        return db_manager.save_webpage_content(content_data)
    
    def _save_error(self, website_id: int, result: Dict[str, Any]):
        """保存错误信息"""
        content_data = {
            'website_id': website_id,
            'content_hash': '',
            'raw_content': '',
            'extracted_content': '',
            'content_length': 0,
            'response_time': result.get('response_time', 0),
            'status_code': result.get('status_code'),
            'error_message': result.get('error', '未知错误')
        }
        
        db_manager.save_webpage_content(content_data)
    
    async def fetch_multiple_websites(self, website_ids: List[int]) -> List[Dict[str, Any]]:
        """并发抓取多个网站"""
        tasks = []
        
        for website_id in website_ids:
            task = asyncio.create_task(self._async_fetch_website(website_id))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'success': False,
                    'error': str(result),
                    'website_id': website_ids[i]
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _async_fetch_website(self, website_id: int) -> Dict[str, Any]:
        """异步抓取单个网站"""
        # 在线程池中执行同步抓取
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.fetch_website, website_id)