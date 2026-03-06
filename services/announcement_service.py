"""
公告识别服务

负责识别消息是否为公告类消息（默认识别 #公告 / #通知）。
"""

from typing import Iterable, List, Optional

from calculator import MetricsCalculator


class AnnouncementService:
    """公告识别服务"""

    DEFAULT_TAGS = ("公告", "通知")

    @staticmethod
    def parse_tags(raw_tags: Optional[str]) -> List[str]:
        """
        解析公告标签配置

        Args:
            raw_tags: 逗号分隔字符串，例如 "公告,通知"

        Returns:
            标签列表（去重、去空）
        """
        if not raw_tags:
            return list(AnnouncementService.DEFAULT_TAGS)

        tags = []
        for part in raw_tags.split(","):
            tag = part.strip()
            if tag and tag not in tags:
                tags.append(tag)
        return tags or list(AnnouncementService.DEFAULT_TAGS)

    @staticmethod
    def is_announcement_text(text: str, tags: Optional[Iterable[str]] = None) -> bool:
        """
        判断纯文本是否包含公告标签（#标签）
        """
        if not text:
            return False

        normalized = text.replace("＃", "#")
        check_tags = list(tags) if tags else list(AnnouncementService.DEFAULT_TAGS)

        for tag in check_tags:
            if f"#{tag}" in normalized:
                return True
        return False

    @staticmethod
    def is_announcement_message(content, tags: Optional[Iterable[str]] = None) -> bool:
        """
        判断消息内容是否为公告消息

        Args:
            content: 飞书消息 content（str 或 dict）
            tags: 标签列表，不传则使用默认值
        """
        text, _ = MetricsCalculator.extract_text_from_content(content)
        return AnnouncementService.is_announcement_text((text or "").strip(), tags)
