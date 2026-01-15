import json
import re
from config import ACTIVITY_WEIGHTS


class MetricsCalculator:
    def __init__(self, messages, user_names=None):
        self.messages = messages
        self.user_names = user_names or {}
        self.msg_sender_map = {}

    def calculate(self):
        metrics = {}

        for msg in self.messages:
            msg_id = msg.get("message_id")
            sender = msg.get("sender", {})

            # 处理 sender.id 可能是字符串或字典的情况
            sender_id_obj = sender.get("id", {})
            if isinstance(sender_id_obj, dict):
                sender_id = sender_id_obj.get("open_id", "")
            elif isinstance(sender_id_obj, str):
                sender_id = sender_id_obj
            else:
                sender_id = ""

            self.msg_sender_map[msg_id] = sender_id

            if sender_id and sender_id not in metrics:
                metrics[sender_id] = {
                    "user_id": sender_id,
                    "user_name": self.user_names.get(sender_id, sender_id),
                    "message_count": 0,
                    "char_count": 0,
                    "reply_received": 0,
                    "mention_received": 0,
                    "topic_initiated": 0,
                    "score": 0,
                }

        for msg in self.messages:
            sender = msg.get("sender", {})

            # 处理 sender.id 可能是字符串或字典的情况
            sender_id_obj = sender.get("id", {})
            if isinstance(sender_id_obj, dict):
                sender_id = sender_id_obj.get("open_id", "")
            elif isinstance(sender_id_obj, str):
                sender_id = sender_id_obj
            else:
                sender_id = ""

            if not sender_id:
                continue

            metrics[sender_id]["message_count"] += 1

            content = msg.get("body", {}).get("content", "")
            char_count = self._extract_text_length(content)
            metrics[sender_id]["char_count"] += char_count

            parent_id = msg.get("parent_id")
            if parent_id and parent_id in self.msg_sender_map:
                original_sender = self.msg_sender_map[parent_id]
                metrics[original_sender]["reply_received"] += 1

            mentions = msg.get("mentions", [])
            for mention in mentions:
                mentioned_id = mention.get("id", {}).get("open_id", "")
                if mentioned_id:
                    metrics[mentioned_id]["mention_received"] += 1

            if not msg.get("root_id"):
                msg_id = msg.get("message_id")
                is_topic = any(m.get("root_id") == msg_id for m in self.messages)
                if is_topic:
                    metrics[sender_id]["topic_initiated"] += 1

        # 计算活跃度分数（使用配置文件中的权重）
        for user_id, data in metrics.items():
            score = (
                data["message_count"] * ACTIVITY_WEIGHTS["message_count"]
                + data["char_count"] * ACTIVITY_WEIGHTS["char_count"]
                + data["reply_received"] * ACTIVITY_WEIGHTS["reply_received"]
                + data["mention_received"] * ACTIVITY_WEIGHTS["mention_received"]
                + data["topic_initiated"] * ACTIVITY_WEIGHTS["topic_initiated"]
            )
            metrics[user_id]["score"] = round(score, 2)

        return dict(metrics)

    def _extract_text_length(self, content):
        text, _ = self.extract_text_from_content(content)
        # 移除 @ 标签带来的字数影响
        text = re.sub(r"@[^ ]+", "", text)
        return len(text.strip())

    @staticmethod
    def extract_text_from_content(content):
        """通用内容提取逻辑，支持 text、post 以及其他复杂类型
        返回: (text_content, image_keys_list)
        """
        if not content:
            return "", []

        try:
            # 如果 content 是字符串，则解析为字典；如果是字典则直接使用
            if isinstance(content, str):
                content_obj = json.loads(content)
            else:
                content_obj = content

            # 1. 尝试直接获取 text 字段 (纯文本消息)
            if "text" in content_obj:
                text = content_obj["text"]
                # 处理被转义的 JSON 文本
                if isinstance(text, str) and text.startswith('{"text":'):
                    try:
                        inner = json.loads(text)
                        return inner.get("text", text), []
                    except (json.JSONDecodeError, ValueError):
                        # 嵌套JSON解析失败，返回原始文本
                        pass
                return text, []

            # 2. 处理直接的 post 结构 (title + content 数组)
            if "content" in content_obj and isinstance(content_obj["content"], list):
                text_parts = []
                image_keys = []

                # 添加标题(如果有)
                if content_obj.get("title"):
                    text_parts.append(content_obj["title"])

                # 遍历每一行 content
                for row in content_obj["content"]:
                    if not isinstance(row, list):
                        continue
                    row_text = []
                    for item in row:
                        if not isinstance(item, dict):
                            continue
                        tag = item.get("tag")
                        if tag in ["text", "a", "at"]:
                            text_val = item.get("text", "")
                            if text_val:
                                row_text.append(text_val)
                        elif tag == "img":
                            # 提取图片 key
                            img_key = item.get("image_key")
                            if img_key:
                                image_keys.append(img_key)
                    if row_text:
                        text_parts.append("".join(row_text))

                return "\n".join(text_parts), image_keys

            # 3. 处理标准的 post 结构 (带语言版本)
            if "post" in content_obj:
                post_data = content_obj["post"]
                text_parts = []
                image_keys = []
                values_to_check = post_data.values() if isinstance(post_data, dict) else [post_data]

                for lang_data in values_to_check:
                    if not isinstance(lang_data, dict):
                        continue

                    if "title" in lang_data and lang_data["title"]:
                        text_parts.append(lang_data["title"])

                    if "content" in lang_data:
                        for row in lang_data["content"]:
                            row_text = []
                            for item in row:
                                tag = item.get("tag")
                                if tag in ["text", "a", "at"]:
                                    text_parts_in_row = item.get("text", "")
                                    if text_parts_in_row:
                                        row_text.append(text_parts_in_row)
                                elif tag == "img":
                                    img_key = item.get("image_key")
                                    if img_key:
                                        image_keys.append(img_key)
                            if row_text:
                                text_parts.append("".join(row_text))

                if text_parts or image_keys:
                    return "\n".join(text_parts), image_keys

            # 4. 处理其他类型 (image, file, audio 等)
            for key in ["image_key", "file_key", "file_name"]:
                if key in content_obj:
                    return f"[{key.replace('_', ' ')}: {content_obj[key]}]", []

            # ⚠️ 兜底逻辑
            if content_obj:
                return str(content_obj), []

            return "", []
        except Exception:
            # 如果解析完全失败，返回原始输入
            return str(content), []
