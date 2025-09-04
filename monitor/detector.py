# 变化检测模块

import re
import difflib
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from bs4 import BeautifulSoup
from loguru import logger
from .config import config
from .database import db_manager, WebsiteModel, WebpageContentModel, ChangeDetectionModel


@dataclass
class ChangeResult:
    """变化检测结果"""
    has_change: bool
    change_type: str
    change_score: float
    change_details: Dict[str, Any]
    old_content_hash: str
    new_content_hash: str
    diff_summary: str
    

class ContentNormalizer:
    """内容标准化器"""
    
    def __init__(self):
        self.ignore_patterns = config.detection.ignore_patterns
        self.whitespace_patterns = [
            r'\s+',  # 多个空白字符
            r'\n+',  # 多个换行符
            r'\t+',  # 多个制表符
        ]
    
    def normalize_content(self, content: str, website_config: WebsiteModel) -> str:
        """标准化内容"""
        if not content:
            return ''
        
        normalized = content
        
        # 移除HTML标签（如果需要）
        if website_config.ignore_html_tags:
            normalized = self._remove_html_tags(normalized)
        
        # 标准化空白字符
        if website_config.ignore_whitespace:
            normalized = self._normalize_whitespace(normalized)
        
        # 移除忽略的模式
        normalized = self._remove_ignore_patterns(normalized, website_config)
        
        # 移除时间戳和动态内容
        if website_config.ignore_timestamps:
            normalized = self._remove_timestamps(normalized)
        
        # 移除数字变化（如果配置）
        if website_config.ignore_numbers:
            normalized = self._remove_numbers(normalized)
        
        return normalized.strip()
    
    def _remove_html_tags(self, content: str) -> str:
        """移除HTML标签"""
        try:
            soup = BeautifulSoup(content, 'lxml')
            return soup.get_text(separator=' ', strip=True)
        except Exception as e:
            logger.warning(f"移除HTML标签失败: {str(e)}")
            return re.sub(r'<[^>]+>', '', content)
    
    def _normalize_whitespace(self, content: str) -> str:
        """标准化空白字符"""
        # 替换多个空白字符为单个空格
        content = re.sub(r'\s+', ' ', content)
        # 移除行首行尾空白
        content = '\n'.join(line.strip() for line in content.split('\n'))
        # 移除多余的空行
        content = re.sub(r'\n\s*\n', '\n', content)
        return content
    
    def _remove_ignore_patterns(self, content: str, website_config: WebsiteModel) -> str:
        """移除忽略的模式"""
        # 全局忽略模式
        for pattern in self.ignore_patterns:
            try:
                content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
            except re.error as e:
                logger.warning(f"忽略模式匹配失败: {pattern}, 错误: {str(e)}")
        
        # 网站特定忽略模式
        if website_config.ignore_patterns:
            for pattern in website_config.ignore_patterns:
                try:
                    content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
                except re.error as e:
                    logger.warning(f"网站忽略模式匹配失败: {pattern}, 错误: {str(e)}")
        
        return content
    
    def _remove_timestamps(self, content: str) -> str:
        """移除时间戳"""
        timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',  # 2023-12-01 12:30:45
            r'\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}',  # 2023/12/01 12:30:45
            r'\d{2}:\d{2}:\d{2}',  # 12:30:45
            r'\d{4}-\d{2}-\d{2}',  # 2023-12-01
            r'\d{4}/\d{2}/\d{2}',  # 2023/12/01
            r'\d{1,2}\s+(分钟|小时|天|周|月|年)前',  # 中文相对时间
            r'\d+\s+(minutes?|hours?|days?|weeks?|months?|years?)\s+ago',  # 英文相对时间
            r'Last updated:?\s*[^\n]*',  # Last updated
            r'更新时间:?\s*[^\n]*',  # 更新时间
        ]
        
        for pattern in timestamp_patterns:
            try:
                content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
            except re.error as e:
                logger.warning(f"时间戳模式匹配失败: {pattern}, 错误: {str(e)}")
        
        return content
    
    def _remove_numbers(self, content: str) -> str:
        """移除数字变化"""
        # 移除独立的数字
        content = re.sub(r'\b\d+\b', '[NUMBER]', content)
        # 移除小数
        content = re.sub(r'\b\d+\.\d+\b', '[DECIMAL]', content)
        return content


class HashDetector:
    """哈希检测器 - 最快速的检测方法"""
    
    def detect_changes(self, old_content: str, new_content: str, website_config: WebsiteModel) -> ChangeResult:
        """检测变化（别名方法）"""
        return self.detect_change(old_content, new_content, website_config)
    
    def detect_change(self, old_content: str, new_content: str, website_config: WebsiteModel) -> ChangeResult:
        """基于哈希的变化检测"""
        normalizer = ContentNormalizer()
        
        # 标准化内容
        old_normalized = normalizer.normalize_content(old_content, website_config)
        new_normalized = normalizer.normalize_content(new_content, website_config)
        
        # 计算哈希
        old_hash = hashlib.sha256(old_normalized.encode('utf-8')).hexdigest()
        new_hash = hashlib.sha256(new_normalized.encode('utf-8')).hexdigest()
        
        has_change = old_hash != new_hash
        
        return ChangeResult(
            has_change=has_change,
            change_type='hash',
            change_score=1.0 if has_change else 0.0,
            change_details={
                'old_length': len(old_normalized),
                'new_length': len(new_normalized),
                'length_diff': len(new_normalized) - len(old_normalized)
            },
            old_content_hash=old_hash,
            new_content_hash=new_hash,
            diff_summary='内容哈希发生变化' if has_change else '内容哈希未变化'
        )


class DiffDetector:
    """差异检测器 - 提供详细的变化信息"""
    
    def detect_change(self, old_content: str, new_content: str, website_config: WebsiteModel) -> ChangeResult:
        """基于差异的变化检测"""
        normalizer = ContentNormalizer()
        
        # 标准化内容
        old_normalized = normalizer.normalize_content(old_content, website_config)
        new_normalized = normalizer.normalize_content(new_content, website_config)
        
        # 计算哈希
        old_hash = hashlib.sha256(old_normalized.encode('utf-8')).hexdigest()
        new_hash = hashlib.sha256(new_normalized.encode('utf-8')).hexdigest()
        
        if old_hash == new_hash:
            return ChangeResult(
                has_change=False,
                change_type='diff',
                change_score=0.0,
                change_details={},
                old_content_hash=old_hash,
                new_content_hash=new_hash,
                diff_summary='内容无变化'
            )
        
        # 计算详细差异
        old_lines = old_normalized.splitlines()
        new_lines = new_normalized.splitlines()
        
        # 使用difflib计算差异
        differ = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile='旧内容',
            tofile='新内容',
            lineterm=''
        )
        
        diff_lines = list(differ)
        
        # 分析变化类型
        added_lines = [line for line in diff_lines if line.startswith('+') and not line.startswith('+++')]
        removed_lines = [line for line in diff_lines if line.startswith('-') and not line.startswith('---')]
        
        # 计算变化分数
        total_lines = max(len(old_lines), len(new_lines), 1)
        changed_lines = len(added_lines) + len(removed_lines)
        change_score = min(changed_lines / total_lines, 1.0)
        
        # 生成差异摘要
        diff_summary = self._generate_diff_summary(added_lines, removed_lines, diff_lines)
        
        return ChangeResult(
            has_change=True,
            change_type='diff',
            change_score=change_score,
            change_details={
                'added_lines': len(added_lines),
                'removed_lines': len(removed_lines),
                'total_changes': changed_lines,
                'change_ratio': change_score,
                'diff_preview': '\n'.join(diff_lines[:20])  # 前20行差异
            },
            old_content_hash=old_hash,
            new_content_hash=new_hash,
            diff_summary=diff_summary
        )
    
    def _generate_diff_summary(self, added_lines: List[str], removed_lines: List[str], diff_lines: List[str]) -> str:
        """生成差异摘要"""
        summary_parts = []
        
        if added_lines:
            summary_parts.append(f"新增 {len(added_lines)} 行")
        
        if removed_lines:
            summary_parts.append(f"删除 {len(removed_lines)} 行")
        
        if not summary_parts:
            return "内容发生变化"
        
        summary = "、".join(summary_parts)
        
        # 添加关键变化预览
        key_changes = []
        for line in added_lines[:3]:
            clean_line = line[1:].strip()  # 移除+号
            if clean_line and len(clean_line) > 10:
                key_changes.append(f"+ {clean_line[:50]}...")
        
        for line in removed_lines[:3]:
            clean_line = line[1:].strip()  # 移除-号
            if clean_line and len(clean_line) > 10:
                key_changes.append(f"- {clean_line[:50]}...")
        
        if key_changes:
            summary += "\n主要变化:\n" + "\n".join(key_changes)
        
        return summary


class SemanticDetector:
    """语义检测器 - 基于内容语义的智能检测"""
    
    def detect_change(self, old_content: str, new_content: str, website_config: WebsiteModel) -> ChangeResult:
        """基于语义的变化检测"""
        normalizer = ContentNormalizer()
        
        # 标准化内容
        old_normalized = normalizer.normalize_content(old_content, website_config)
        new_normalized = normalizer.normalize_content(new_content, website_config)
        
        # 计算哈希
        old_hash = hashlib.sha256(old_normalized.encode('utf-8')).hexdigest()
        new_hash = hashlib.sha256(new_normalized.encode('utf-8')).hexdigest()
        
        if old_hash == new_hash:
            return ChangeResult(
                has_change=False,
                change_type='semantic',
                change_score=0.0,
                change_details={},
                old_content_hash=old_hash,
                new_content_hash=new_hash,
                diff_summary='内容无变化'
            )
        
        # 提取关键信息
        old_features = self._extract_semantic_features(old_normalized)
        new_features = self._extract_semantic_features(new_normalized)
        
        # 计算语义相似度
        similarity_score = self._calculate_semantic_similarity(old_features, new_features)
        change_score = 1.0 - similarity_score
        
        # 分析变化类型
        change_analysis = self._analyze_semantic_changes(old_features, new_features)
        
        return ChangeResult(
            has_change=change_score > config.detection.semantic_threshold,
            change_type='semantic',
            change_score=change_score,
            change_details={
                'similarity_score': similarity_score,
                'semantic_analysis': change_analysis,
                'old_features': old_features,
                'new_features': new_features
            },
            old_content_hash=old_hash,
            new_content_hash=new_hash,
            diff_summary=self._generate_semantic_summary(change_analysis, change_score)
        )
    
    def _extract_semantic_features(self, content: str) -> Dict[str, Any]:
        """提取语义特征"""
        features = {
            'word_count': len(content.split()),
            'char_count': len(content),
            'line_count': len(content.splitlines()),
            'keywords': set(),
            'numbers': [],
            'urls': [],
            'emails': [],
            'sentences': []
        }
        
        # 提取关键词（简单实现）
        words = re.findall(r'\b\w{3,}\b', content.lower())
        features['keywords'] = set(words)
        
        # 提取数字
        numbers = re.findall(r'\b\d+(?:\.\d+)?\b', content)
        features['numbers'] = [float(n) for n in numbers]
        
        # 提取URL
        urls = re.findall(r'https?://[^\s]+', content)
        features['urls'] = urls
        
        # 提取邮箱
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
        features['emails'] = emails
        
        # 提取句子
        sentences = re.split(r'[.!?。！？]', content)
        features['sentences'] = [s.strip() for s in sentences if s.strip()]
        
        return features
    
    def _calculate_semantic_similarity(self, old_features: Dict[str, Any], new_features: Dict[str, Any]) -> float:
        """计算语义相似度"""
        similarities = []
        
        # 关键词相似度
        old_keywords = old_features['keywords']
        new_keywords = new_features['keywords']
        if old_keywords or new_keywords:
            intersection = len(old_keywords & new_keywords)
            union = len(old_keywords | new_keywords)
            keyword_sim = intersection / union if union > 0 else 0
            similarities.append(keyword_sim)
        
        # 结构相似度
        old_structure = (old_features['word_count'], old_features['line_count'])
        new_structure = (new_features['word_count'], new_features['line_count'])
        
        if old_structure[0] > 0 and old_structure[1] > 0:
            word_ratio = min(old_structure[0], new_structure[0]) / max(old_structure[0], new_structure[0])
            line_ratio = min(old_structure[1], new_structure[1]) / max(old_structure[1], new_structure[1])
            structure_sim = (word_ratio + line_ratio) / 2
            similarities.append(structure_sim)
        
        # 数字相似度
        old_numbers = set(old_features['numbers'])
        new_numbers = set(new_features['numbers'])
        if old_numbers or new_numbers:
            intersection = len(old_numbers & new_numbers)
            union = len(old_numbers | new_numbers)
            number_sim = intersection / union if union > 0 else 0
            similarities.append(number_sim)
        
        # URL和邮箱相似度
        old_urls = set(old_features['urls'])
        new_urls = set(new_features['urls'])
        if old_urls or new_urls:
            intersection = len(old_urls & new_urls)
            union = len(old_urls | new_urls)
            url_sim = intersection / union if union > 0 else 0
            similarities.append(url_sim)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _analyze_semantic_changes(self, old_features: Dict[str, Any], new_features: Dict[str, Any]) -> Dict[str, Any]:
        """分析语义变化"""
        analysis = {
            'content_growth': new_features['word_count'] - old_features['word_count'],
            'new_keywords': list(new_features['keywords'] - old_features['keywords']),
            'removed_keywords': list(old_features['keywords'] - new_features['keywords']),
            'new_urls': list(set(new_features['urls']) - set(old_features['urls'])),
            'removed_urls': list(set(old_features['urls']) - set(new_features['urls'])),
            'number_changes': {
                'added': list(set(new_features['numbers']) - set(old_features['numbers'])),
                'removed': list(set(old_features['numbers']) - set(new_features['numbers']))
            }
        }
        
        return analysis
    
    def _generate_semantic_summary(self, analysis: Dict[str, Any], change_score: float) -> str:
        """生成语义变化摘要"""
        summary_parts = []
        
        if analysis['content_growth'] > 0:
            summary_parts.append(f"内容增加 {analysis['content_growth']} 个词")
        elif analysis['content_growth'] < 0:
            summary_parts.append(f"内容减少 {abs(analysis['content_growth'])} 个词")
        
        if analysis['new_keywords']:
            summary_parts.append(f"新增关键词: {', '.join(analysis['new_keywords'][:5])}")
        
        if analysis['removed_keywords']:
            summary_parts.append(f"移除关键词: {', '.join(analysis['removed_keywords'][:5])}")
        
        if analysis['new_urls']:
            summary_parts.append(f"新增链接 {len(analysis['new_urls'])} 个")
        
        if not summary_parts:
            summary_parts.append(f"语义变化分数: {change_score:.2f}")
        
        return "；".join(summary_parts)


class ChangeDetector:
    """变化检测器主类"""
    
    def __init__(self):
        self.hash_detector = HashDetector()
        self.diff_detector = DiffDetector()
        self.semantic_detector = SemanticDetector()
    
    def detect_website_changes(self, website_id: int) -> Optional[ChangeResult]:
        """检测网站变化"""
        try:
            # 获取网站配置
            website = db_manager.get_website(website_id)
            if not website:
                logger.error(f"网站不存在 - ID: {website_id}")
                return None
            
            # 获取最新的两次内容
            contents = db_manager.get_latest_contents(website_id, limit=2)
            if len(contents) < 2:
                logger.info(f"网站内容不足2次，无法进行变化检测 - ID: {website_id}")
                return None
            
            new_content = contents[0]
            old_content = contents[1]
            
            # 如果有错误，跳过检测
            if new_content.error_message or old_content.error_message:
                logger.info(f"内容包含错误，跳过变化检测 - ID: {website_id}")
                return None
            
            logger.info(f"开始检测网站变化 - ID: {website_id}, 算法: {website.detection_algorithm}")
            
            # 选择检测算法
            if website.detection_algorithm == 'hash':
                result = self.hash_detector.detect_change(
                    old_content.extracted_content,
                    new_content.extracted_content,
                    website
                )
            elif website.detection_algorithm == 'diff':
                result = self.diff_detector.detect_change(
                    old_content.extracted_content,
                    new_content.extracted_content,
                    website
                )
            elif website.detection_algorithm == 'semantic':
                result = self.semantic_detector.detect_change(
                    old_content.extracted_content,
                    new_content.extracted_content,
                    website
                )
            else:
                logger.error(f"未知的检测算法: {website.detection_algorithm}")
                return None
            
            # 保存检测结果
            if result.has_change:
                detection_id = self._save_change_detection(website_id, new_content.id, old_content.id, result)
                result.change_details['detection_id'] = detection_id
                
                logger.info(f"检测到变化 - ID: {website_id}, 变化分数: {result.change_score:.3f}")
            else:
                logger.info(f"未检测到变化 - ID: {website_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"变化检测异常 - ID: {website_id}, 错误: {str(e)}")
            return None
    
    def _save_change_detection(self, website_id: int, new_content_id: int, old_content_id: int, result: ChangeResult) -> int:
        """保存变化检测结果"""
        detection_data = {
            'website_id': website_id,
            'new_content_id': new_content_id,
            'old_content_id': old_content_id,
            'change_type': result.change_type,
            'change_score': result.change_score,
            'change_details': json.dumps(result.change_details, ensure_ascii=False),
            'diff_summary': result.diff_summary,
            'old_content_hash': result.old_content_hash,
            'new_content_hash': result.new_content_hash
        }
        
        return db_manager.save_change_detection(detection_data)
    
    def get_change_history(self, website_id: int, limit: int = 50) -> List[ChangeDetectionModel]:
        """获取变化历史"""
        return db_manager.get_change_history(website_id, limit)
    
    def get_change_statistics(self, website_id: int, days: int = 30) -> Dict[str, Any]:
        """获取变化统计"""
        changes = db_manager.get_recent_changes(website_id, days)
        
        if not changes:
            return {
                'total_changes': 0,
                'avg_change_score': 0.0,
                'change_frequency': 0.0,
                'change_types': {}
            }
        
        total_changes = len(changes)
        avg_score = sum(change.change_score for change in changes) / total_changes
        change_frequency = total_changes / days
        
        # 统计变化类型
        change_types = {}
        for change in changes:
            change_type = change.change_type
            if change_type not in change_types:
                change_types[change_type] = 0
            change_types[change_type] += 1
        
        return {
            'total_changes': total_changes,
            'avg_change_score': avg_score,
            'change_frequency': change_frequency,
            'change_types': change_types,
            'latest_change': changes[0].created_at if changes else None
        }


# 全局检测器实例
change_detector = ChangeDetector()