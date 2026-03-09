$file = 'B:\Projects\feishu\pin_daily_audit.py'
$content = Get-Content $file -Raw

$oldImports = @"
import json
import os
"@
$newImports = @"
import html
import json
import os
import re
"@
$content = $content.Replace($oldImports, $newImports)

$oldConstants = @"
    PIN_SUMMARY_PREVIEW_COUNT = 2
    PIN_SUMMARY_PREVIEW_LENGTH = 50
    PIN_SUMMARY_COLLAPSIBLE_TITLE = "展开查看全部帖子"
"@
$newConstants = @"
    PIN_SUMMARY_PREVIEW_LENGTH = 50
    PIN_SUMMARY_COLLAPSIBLE_TITLE = "展开查看全部帖子"
    SECTION_LABELS = {
        1: "一",
        2: "二",
        3: "三",
        4: "四",
        5: "五",
        6: "六",
        7: "七",
        8: "八",
        9: "九",
        10: "十",
    }
"@
$content = $content.Replace($oldConstants, $newConstants)

$oldReturn = @"
        return {
            "message_id": message_id,
            "sender_name": sender_name,
            "operator_name": operator_name,
            "post_time": msg_create_time_str,
            "pin_time": pin_time_str,
            "content": content or "[无文本内容]",
        }
"@
$newReturn = @"
        return {
            "message_id": message_id,
            "sender_name": sender_name,
            "operator_name": operator_name,
            "post_time": msg_create_time_str,
            "pin_time": pin_time_str,
            "content": content or "[无文本内容]",
            "raw_content": detail.get("raw_content", ""),
        }
"@
if (-not $content.Contains($oldReturn)) { throw 'process return block not found' }
$content = $content.Replace($oldReturn, $newReturn)

$start = $content.IndexOf("    def _format_post_time_for_card(self, post_time: str) -> str:")
$end = $content.IndexOf("    def _send_summary_card(self, items: List[dict], card_title: str) -> None:")
if ($start -lt 0 -or $end -lt 0 -or $end -le $start) { throw 'method block markers not found' }
$newBlock = @"
    def _format_post_time_for_card(self, post_time: str) -> str:
        """将帖子发送时间压缩为卡片展示格式。"""
        if post_time and len(post_time) >= 16:
            return post_time[5:16]
        return post_time or ""

    @staticmethod
    def _normalize_card_text(text: str) -> str:
        """规范化卡片文本，保留分段并压缩过多空行。"""
        normalized = html.unescape(str(text or "")).replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[ \t]+\n", "\n", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    @classmethod
    def _escape_card_markdown_text(cls, text: str) -> str:
        """转义普通文本中的 markdown 控制字符，同时尽量保留列表语义。"""
        normalized = cls._normalize_card_text(text)
        if not normalized:
            return ""

        escaped_lines = []
        for line in normalized.split("\n"):
            escaped = line.replace("\\", "\\\\")
            escaped = escaped.replace("`", "\\`")
            escaped = escaped.replace("[", "\\[").replace("]", "\\]")
            escaped = escaped.replace("(", "\\(").replace(")", "\\)")
            escaped = escaped.replace("*", "\\*").replace("_", "\\_").replace("~", "\\~")
            escaped = re.sub(r"^(#+)", lambda match: "".join(r"\\#" for _ in match.group(1)), escaped)
            if escaped.startswith(">"):
                escaped = f"\\{escaped}"
            escaped_lines.append(escaped)

        return "\n".join(escaped_lines)

    @staticmethod
    def _parse_raw_content_object(raw_content) -> dict:
        """解析消息 raw_content，失败时回退为 text 消息。"""
        if isinstance(raw_content, dict):
            return raw_content

        if isinstance(raw_content, str):
            try:
                return json.loads(raw_content)
            except Exception:
                return {"text": raw_content}

        return {}

    @staticmethod
    def _extract_text_payload(content_obj: dict) -> str:
        """提取 text 消息正文，兼容嵌套 JSON。"""
        text = content_obj.get("text", "")
        if isinstance(text, str) and text.startswith('{"text":'):
            try:
                text = json.loads(text).get("text", text)
            except Exception:
                pass
        return str(text or "")

    @staticmethod
    def _extract_localized_post_content(content_obj: dict) -> Optional[dict]:
        """抽取 post 富文本的当前语言内容。"""
        if isinstance(content_obj.get("post"), dict):
            post_obj = content_obj["post"]
            if isinstance(post_obj.get("zh_cn"), dict):
                return post_obj["zh_cn"]
            return next((value for value in post_obj.values() if isinstance(value, dict)), None)

        if isinstance(content_obj.get("content"), list):
            return content_obj

        return None

    @staticmethod
    def _apply_card_text_styles(text: str, styles: Optional[List[str]], un_styles: Optional[List[str]]) -> str:
        """将飞书文本样式映射为卡片 markdown。"""
        if not text:
            return ""

        active_styles = set(styles or []) - set(un_styles or [])
        styled = text
        if "bold" in active_styles:
            styled = f"**{styled}**"
        if "italic" in active_styles:
            styled = f"*{styled}*"
        if "lineThrough" in active_styles:
            styled = f"~~{styled}~~"
        return styled

    def _render_rich_item_to_markdown(self, item: dict) -> str:
        """将飞书富文本元素转换为卡片 markdown。"""
        if not isinstance(item, dict):
            return ""

        tag = item.get("tag", "text")
        if tag == "text":
            text = self._escape_card_markdown_text(item.get("text", ""))
            return self._apply_card_text_styles(text, item.get("style"), item.get("un_style"))

        if tag == "a":
            link_text = self._escape_card_markdown_text(item.get("text") or item.get("href") or "链接")
            href = (item.get("href") or "").strip()
            return f"[{link_text}]({href})" if href else link_text

        if tag == "at":
            user_name = item.get("user_name") or item.get("text") or item.get("user_id") or "未知用户"
            return self._escape_card_markdown_text(f"@{user_name}")

        if tag == "md":
            return self._normalize_card_text(item.get("text", ""))

        if tag == "img":
            return "[图片]"

        if tag == "file":
            return "[附件]"

        if tag == "emotion":
            return self._escape_card_markdown_text(item.get("text") or item.get("emoji_type") or "[表情]")

        fallback_text = item.get("text") or item.get("content") or ""
        return self._escape_card_markdown_text(str(fallback_text)) if fallback_text else ""

    def _render_raw_content_to_card_markdown(self, raw_content) -> str:
        """将消息原始内容转换为卡片可读 markdown。"""
        content_obj = self._parse_raw_content_object(raw_content)
        post_content = self._extract_localized_post_content(content_obj)

        if post_content:
            paragraphs: List[str] = []
            title = self._escape_card_markdown_text(post_content.get("title", ""))
            if title:
                paragraphs.append(title)

            for row in post_content.get("content", []):
                if not isinstance(row, list):
                    continue
                row_markdown = "".join(
                    part for part in (self._render_rich_item_to_markdown(item) for item in row) if part
                ).strip()
                if row_markdown:
                    paragraphs.append(row_markdown)

            rendered = "\n\n".join(paragraphs).strip()
            if rendered:
                return rendered

        text_payload = self._extract_text_payload(content_obj)
        if text_payload:
            return self._escape_card_markdown_text(text_payload)

        if content_obj.get("image_key"):
            return "[图片]"

        if content_obj.get("file_key") or content_obj.get("file_name"):
            return "[附件]"

        fallback = self._escape_card_markdown_text(str(raw_content or ""))
        return fallback or "[无文本内容]"

    @staticmethod
    def _markdown_to_plain_text(markdown_text: str) -> str:
        """去掉 markdown 标记，用于预览和长度判定。"""
        plain_text = html.unescape(str(markdown_text or ""))
        plain_text = re.sub(r"!\[([^\]]*)\]\([^\)]*\)", r"\1", plain_text)
        plain_text = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", plain_text)
        plain_text = plain_text.replace("**", "").replace("~~", "").replace("`", "")
        plain_text = re.sub(r"(?<!\*)\*(?!\*)", "", plain_text)
        plain_text = re.sub(r"\\([\\`*_\[\]()#+\-.!~>])", r"\1", plain_text)
        plain_text = re.sub(r"\n{3,}", "\n\n", plain_text)
        return plain_text.strip()

    def _build_preview_plain_text(self, item: dict) -> str:
        """构建折叠前预览文案。"""
        plain_text = self._markdown_to_plain_text(self._get_item_card_markdown(item))
        plain_text = re.sub(r"\s+", " ", plain_text).strip()
        if not plain_text:
            return "[无文本内容]"
        if len(plain_text) > self.PIN_SUMMARY_PREVIEW_LENGTH:
            return f"{plain_text[:self.PIN_SUMMARY_PREVIEW_LENGTH]}..."
        return plain_text

    def _get_item_card_markdown(self, item: dict) -> str:
        """获取单条帖子用于卡片展示的完整 markdown。"""
        raw_content = item.get("raw_content", "")
        markdown = self._render_raw_content_to_card_markdown(raw_content)
        if markdown:
            return markdown
        fallback = self._escape_card_markdown_text(item.get("content") or "")
        return fallback or "[无文本内容]"

    @classmethod
    def _format_post_section_name(cls, index: int) -> str:
        """格式化帖子分隔标题。"""
        section_label = cls.SECTION_LABELS.get(index)
        if section_label:
            return f"帖子{section_label}"
        return f"帖子{index}"

    def _build_post_section_heading(self, index: int, item: dict) -> str:
        """构建帖子分隔标题。"""
        post_time = item.get("post_time") or item.get("create_time") or ""
        sender_name = self._escape_card_markdown_text(item.get("sender_name") or "未知用户")
        return f"**【{self._format_post_section_name(index)}】{sender_name}（{self._format_post_time_for_card(post_time)}）**"

    def _build_post_preview_markdown(self, index: int, item: dict) -> str:
        """构建单条帖子折叠前预览。"""
        heading = self._build_post_section_heading(index, item)
        preview_text = self._escape_card_markdown_text(self._build_preview_plain_text(item))
        return f"{heading}\n{preview_text}"

    def _build_post_detail_markdown(self, index: int, item: dict) -> str:
        """构建单条帖子的完整展示 markdown。"""
        heading = self._build_post_section_heading(index, item)
        body_markdown = self._get_item_card_markdown(item)
        return f"{heading}\n\n{body_markdown}" if body_markdown else heading

    def _build_post_markdown_elements(self, items: List[dict], preview: bool = False) -> List[dict]:
        """构建帖子内容元素列表。"""
        elements: List[dict] = []
        for index, item in enumerate(items, 1):
            content = (
                self._build_post_preview_markdown(index, item)
                if preview
                else self._build_post_detail_markdown(index, item)
            )
            elements.append({"tag": "markdown", "content": content})
            if index < len(items):
                elements.append({"tag": "hr"})
        return elements

    def _build_summary_preview_elements(self, items: List[dict]) -> List[dict]:
        """构建折叠前的摘要和全部帖子预览。"""
        elements = [{"tag": "markdown", "content": f"本次新增 {len(items)} 条 Pin"}]
        elements.extend(self._build_post_markdown_elements(items, preview=True))
        return elements

    def _get_summary_visible_length(self, items: List[dict]) -> int:
        """按可见正文长度判断是否需要折叠。"""
        return sum(len(re.sub(r"\s+", " ", self._markdown_to_plain_text(self._get_item_card_markdown(item))).strip()) for item in items)

    def _build_summary_card_payload(self, items: List[dict], card_title: str) -> dict:
        """构建 Pin 汇总卡片 payload。"""
        detail_elements = self._build_post_markdown_elements(items)

        if self._get_summary_visible_length(items) > self.PIN_SUMMARY_COLLAPSE_THRESHOLD:
            body_elements = self._build_summary_preview_elements(items)
            body_elements.append(
                {
                    "tag": "collapsible_panel",
                    "expanded": False,
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": self.PIN_SUMMARY_COLLAPSIBLE_TITLE,
                        },
                        "icon": {
                            "tag": "standard_icon",
                            "token": "down-small-ccm_outlined",
                            "size": "16px 16px",
                        },
                        "icon_position": "right",
                    },
                    "elements": detail_elements,
                }
            )
        else:
            body_elements = detail_elements

        return {
            "schema": "2.0",
            "config": {
                "wide_screen_mode": True,
                "update_multi": True,
            },
            "header": {
                "template": "orange",
                "title": {"tag": "plain_text", "content": card_title},
            },
            "body": {
                "elements": body_elements,
            },
        }

"@
$content = $content.Substring(0, $start) + $newBlock + $content.Substring($end)
Set-Content $file $content -NoNewline
