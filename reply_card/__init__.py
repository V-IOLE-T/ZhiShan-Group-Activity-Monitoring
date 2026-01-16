"""
飞书云文档卡片推送模块

实现“提取链接 -> MCP获取内容 -> 生成卡片 -> 推送”的完整流程
"""

from .processor import DocCardProcessor

__all__ = ["DocCardProcessor"]
