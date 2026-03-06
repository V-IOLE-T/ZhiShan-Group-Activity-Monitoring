"""
Pin 审计任务

当前调度策略为每周一 09:00 扫描“上周新增 Pin（按 Pin 操作时间）”，并对新增且未处理的消息执行：
1. 归档 Pin 记录
2. 给被 Pin 用户增加被 Pin 次数
3. 写入精华文档（可选）
4. 群内发送 1 张汇总提醒卡片（仅在有新增时）
"""

import json
import os
from datetime import datetime, timedelta, time as dtime
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests

from calculator import MetricsCalculator
from collector import MessageCollector
from message_renderer import MessageToDocxConverter


class DailyPinAuditor:
    """Pin 审计器（主流程为每周审计）"""

    PROCESSED_FILE = Path(__file__).parent / ".processed_daily_pins.txt"
    MAX_PIN_PAGE_SIZE = 50

    def __init__(self, auth, storage, chat_id: str, docx_storage=None, essence_doc_token: str = None):
        self.auth = auth
        self.storage = storage
        self.chat_id = chat_id
        self.docx_storage = docx_storage
        self.essence_doc_token = essence_doc_token
        self.collector = MessageCollector(auth)
        self.user_name_cache: Dict[str, str] = {}
        self.converter = MessageToDocxConverter(docx_storage) if docx_storage else None
        self.processed_ids: Set[str] = self._load_processed_ids()

        if not os.getenv("PIN_TABLE_ID"):
            print("⚠️  未配置 PIN_TABLE_ID：Pin 审计任务将跳过 Pin 归档表写入")

    def run_for_last_week(self) -> int:
        """
        执行“上周 Pin 审计”

        Returns:
            成功处理的 Pin 数量
        """
        last_week_start, last_week_end = self._get_last_week_window()
        week_end_date = (last_week_end - timedelta(days=1)).date().isoformat()
        card_title = f"📌 上周加精 ({last_week_start.date().isoformat()} ~ {week_end_date})"
        return self._run_for_window(
            window_start=last_week_start,
            window_end=last_week_end,
            window_name="上周",
            outside_window_name="非上周窗口",
            card_title=card_title,
        )

    def run_for_yesterday(self) -> int:
        """
        执行“昨日 Pin 审计”（兼容旧接口，不走主调度链路）

        Returns:
            成功处理的 Pin 数量
        """
        yesterday_start, yesterday_end = self._get_yesterday_window()
        card_title = f"📌 昨日加精 ({yesterday_start.date().isoformat()})"
        return self._run_for_window(
            window_start=yesterday_start,
            window_end=yesterday_end,
            window_name="昨日",
            outside_window_name="非昨日窗口",
            card_title=card_title,
        )

    def _run_for_window(
        self,
        window_start: datetime,
        window_end: datetime,
        window_name: str,
        outside_window_name: str,
        card_title: str,
    ) -> int:
        if not self.chat_id:
            print(f"❌ 未配置 CHAT_ID，跳过{window_name} Pin 审计")
            return 0

        pins = self._get_pinned_messages()
        if pins is None:
            return 0

        window_start_ms = int(window_start.timestamp() * 1000)
        window_end_ms = int(window_end.timestamp() * 1000)

        candidates = []
        skipped_processed = 0
        skipped_outside_window = 0
        skipped_invalid_time = 0
        for pin in pins:
            message_id = pin.get("message_id")
            pin_time_raw = pin.get("create_time") or pin.get("pin_time") or pin.get("time")
            pin_time_ms = self._normalize_timestamp_ms(self._safe_int(pin_time_raw))
            if not message_id:
                continue
            if message_id in self.processed_ids:
                skipped_processed += 1
                continue
            if pin_time_ms <= 0:
                skipped_invalid_time += 1
                continue
            if window_start_ms <= pin_time_ms < window_end_ms:
                candidates.append(pin)
            else:
                skipped_outside_window += 1

        if not candidates:
            print(
                f"📌 {window_name}无新增 Pin（或均已处理），不发送提醒"
                f" | 已处理: {skipped_processed}, {outside_window_name}: {skipped_outside_window}, 无效时间: {skipped_invalid_time}"
            )
            return 0

        print(f"📌 {window_name}新增 Pin 待处理: {len(candidates)} 条")

        processed_items = []
        newly_processed_ids = set()

        for pin in candidates:
            item = self._process_one_pin(pin)
            if item:
                processed_items.append(item)
                newly_processed_ids.add(item["message_id"])

        if not processed_items:
            print(f"⚠️ {window_name} Pin 候选存在，但未成功处理任何记录")
            return 0

        # 保存处理记录（去重保证：同一 message_id 只处理一次）
        self.processed_ids.update(newly_processed_ids)
        self._save_processed_ids(self.processed_ids)

        # 仅在有新增时发送 1 张汇总卡片
        self._send_summary_card(processed_items, card_title)
        print(f"✅ {window_name} Pin 审计完成：成功处理 {len(processed_items)} 条")
        return len(processed_items)

    def _process_one_pin(self, pin: dict) -> Optional[dict]:
        """处理单条 Pin"""
        message_id = pin.get("message_id")
        if not message_id:
            return None

        operator_id = self._extract_user_id(pin.get("operator_id"))
        pin_time_raw = pin.get("create_time") or pin.get("pin_time") or pin.get("time")
        pin_time_ms = self._normalize_timestamp_ms(self._safe_int(pin_time_raw))
        pin_time_str = self._format_ms(pin_time_ms)

        detail = self._get_message_detail(message_id)
        if not detail:
            return None

        sender_id = detail.get("sender_id")
        if not sender_id:
            print(f"⚠️ 跳过 {message_id}：无法解析发送者")
            return None

        sender_name = self._get_user_name(sender_id)
        operator_name = self._get_user_name(operator_id) if operator_id else "管理员"
        msg_create_time_str = self._format_ms(self._safe_int(detail.get("create_time")))

        # 附件处理（用于 Pin 归档表）
        file_tokens = self._collect_file_tokens(message_id, detail)

        pin_info = {
            "message_id": message_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "operator_id": operator_id,
            "operator_name": operator_name,
            "pin_time": pin_time_str,
            "message_type": detail.get("message_type", "text"),
            "content": detail.get("content", ""),
            "create_time": msg_create_time_str,
            "archive_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_tokens": file_tokens,
        }

        # 1) 归档 Pin 记录（依赖 PIN_TABLE_ID）
        if hasattr(self.storage, "archive_pin_message"):
            self.storage.archive_pin_message(pin_info)

        # 2) 增加被 Pin 次数
        if hasattr(self.storage, "increment_pin_count"):
            self.storage.increment_pin_count(sender_id, sender_name)

        # 3) 写入精华文档（可选）
        if self.converter and self.docx_storage and self.essence_doc_token:
            try:
                blocks = self.converter.convert(
                    detail.get("raw_content", ""),
                    message_id,
                    self.essence_doc_token,
                    sender_name=sender_name,
                    send_time=msg_create_time_str,
                )
                self.docx_storage.add_blocks(self.essence_doc_token, blocks)
            except Exception as e:
                print(f"⚠️ 精华文档写入失败({message_id}): {e}")

        content = (detail.get("content") or "").strip()

        return {
            "message_id": message_id,
            "sender_name": sender_name,
            "operator_name": operator_name,
            "pin_time": pin_time_str,
            "content": content or "[无文本内容]",
        }

    def _send_summary_card(self, items: List[dict], card_title: str) -> None:
        """发送 Pin 汇总卡片（1张）"""
        detail_lines = []
        for i, item in enumerate(items, 1):
            pin_time = item.get("pin_time", "")
            pin_time_display = pin_time[5:16] if len(pin_time) >= 16 else pin_time
            detail_lines.append(
                f"{i}. {item['sender_name']}（{pin_time_display}）\n{item['content']}"
            )
        detail_text = "\n".join(detail_lines)

        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "orange",
                "title": {"tag": "plain_text", "content": card_title},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": detail_text,
                    },
                },
            ],
        }

        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        params = {"receive_id_type": "chat_id"}
        body = {
            "receive_id": self.chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card, ensure_ascii=False),
        }

        try:
            resp = requests.post(url, headers=self.auth.get_headers(), params=params, json=body, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                print("✅ Pin 汇总卡片发送成功")
            else:
                print(f"❌ Pin 汇总卡片发送失败: {data.get('msg')}")
        except Exception as e:
            print(f"❌ Pin 汇总卡片发送异常: {e}")

    def _collect_file_tokens(self, message_id: str, detail: dict) -> List[dict]:
        """收集附件并上传为可归档 token"""
        file_tokens: List[dict] = []

        for image_key in detail.get("image_keys", []):
            token = self._download_and_upload_resource(message_id, image_key, "image", f"{image_key}.png")
            if token:
                file_tokens.append(token)

        if detail.get("message_type") == "image" and detail.get("image_key"):
            image_key = detail.get("image_key")
            token = self._download_and_upload_resource(message_id, image_key, "image", f"{image_key}.png")
            if token:
                file_tokens.append(token)

        if detail.get("message_type") == "file" and detail.get("file_key"):
            file_key = detail.get("file_key")
            file_name = detail.get("file_name", "file")
            token = self._download_and_upload_resource(message_id, file_key, "file", file_name)
            if token:
                file_tokens.append(token)

        return file_tokens

    def _get_pinned_messages(self) -> Optional[List[dict]]:
        url = "https://open.feishu.cn/open-apis/im/v1/pins"
        page_token = None
        all_items: List[dict] = []

        try:
            while True:
                params = {"chat_id": self.chat_id, "page_size": self.MAX_PIN_PAGE_SIZE}
                if page_token:
                    params["page_token"] = page_token

                resp = requests.get(url, headers=self.auth.get_headers(), params=params, timeout=10)
                data = resp.json()
                if data.get("code") != 0:
                    print(f"❌ 获取 Pin 列表失败: {data.get('msg')}")
                    return None

                page_items = data.get("data", {}).get("items", [])
                all_items.extend(page_items)
                page_token = data.get("data", {}).get("page_token")
                if not page_token:
                    break

            print(f"📌 当前 Pin 总数: {len(all_items)}")
            return all_items
        except Exception as e:
            print(f"❌ 获取 Pin 列表异常: {e}")
            return None

    def _get_message_detail(self, message_id: str) -> Optional[dict]:
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
        try:
            resp = requests.get(url, headers=self.auth.get_headers(), timeout=10)
            data = resp.json()
            if data.get("code") != 0:
                print(f"❌ 获取消息详情失败({message_id}): {data.get('msg')}")
                return None

            items = data.get("data", {}).get("items", [])
            if not items:
                return None

            msg = items[0]
            sender_obj = msg.get("sender", {}).get("id")
            sender_id = self._extract_user_id(sender_obj)
            message_type = msg.get("msg_type", "text")
            raw_content = msg.get("body", {}).get("content", "")
            content, image_keys = MetricsCalculator.extract_text_from_content(raw_content)

            try:
                content_obj = json.loads(raw_content) if isinstance(raw_content, str) else (raw_content or {})
            except Exception:
                content_obj = {}

            return {
                "sender_id": sender_id,
                "message_type": message_type,
                "content": content,
                "raw_content": raw_content,
                "create_time": msg.get("create_time"),
                "image_keys": image_keys,
                "file_key": content_obj.get("file_key"),
                "file_name": content_obj.get("file_name"),
                "image_key": content_obj.get("image_key"),
            }
        except Exception as e:
            print(f"❌ 获取消息详情异常({message_id}): {e}")
            return None

    def _get_user_name(self, user_id: Optional[str]) -> str:
        if not user_id:
            return "未知用户"
        if user_id in self.user_name_cache:
            return self.user_name_cache[user_id]

        try:
            names = self.collector.get_user_names([user_id])
            if names and names.get(user_id):
                self.user_name_cache[user_id] = names[user_id]
                return names[user_id]
        except Exception as e:
            print(f"⚠️ 获取用户名失败({user_id}): {e}")

        self.user_name_cache[user_id] = user_id
        return user_id

    def _download_and_upload_resource(
        self, message_id: str, file_key: str, resource_type: str, file_name: str
    ) -> Optional[dict]:
        download_url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}"
        params = {"type": resource_type}

        try:
            resp = requests.get(download_url, headers=self.auth.get_headers(), params=params, timeout=30)
            if resp.status_code != 200:
                print(f"⚠️ 下载资源失败({message_id}): HTTP {resp.status_code}")
                return None
            return self._upload_to_drive(resp.content, file_name)
        except Exception as e:
            print(f"⚠️ 下载资源异常({message_id}): {e}")
            return None

    def _upload_to_drive(self, file_content: bytes, file_name: str) -> Optional[dict]:
        url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        app_token = os.getenv("BITABLE_APP_TOKEN")
        if not app_token:
            return None

        form_data = {
            "file_name": file_name,
            "parent_type": "bitable_file",
            "parent_node": app_token,
            "size": str(len(file_content)),
        }
        files = {"file": (file_name, file_content)}
        headers = {"Authorization": self.auth.get_headers()["Authorization"]}

        try:
            resp = requests.post(url, headers=headers, data=form_data, files=files, timeout=60)
            result = resp.json()
            if result.get("code") != 0:
                return None
            file_token = result.get("data", {}).get("file_token")
            if not file_token:
                return None
            return {
                "file_token": file_token,
                "name": file_name,
                "size": len(file_content),
                "type": "file",
            }
        except Exception:
            return None

    def _load_processed_ids(self) -> Set[str]:
        if not self.PROCESSED_FILE.exists():
            return set()
        try:
            with open(self.PROCESSED_FILE, "r", encoding="utf-8") as f:
                return {line.strip() for line in f if line.strip()}
        except Exception as e:
            print(f"⚠️ 读取已处理 Pin 记录失败: {e}")
            return set()

    def _save_processed_ids(self, ids: Set[str]) -> None:
        try:
            with open(self.PROCESSED_FILE, "w", encoding="utf-8") as f:
                for message_id in sorted(ids):
                    f.write(f"{message_id}\n")
        except Exception as e:
            print(f"⚠️ 保存已处理 Pin 记录失败: {e}")

    @staticmethod
    def _extract_user_id(user_obj) -> Optional[str]:
        if isinstance(user_obj, str):
            return user_obj
        if isinstance(user_obj, dict):
            return user_obj.get("open_id") or user_obj.get("user_id") or user_obj.get("union_id")
        return None

    @staticmethod
    def _safe_int(value) -> int:
        try:
            return int(value)
        except Exception:
            return 0

    @staticmethod
    def _normalize_timestamp_ms(ts: int) -> int:
        """将时间戳统一为毫秒（兼容秒级时间戳）"""
        if ts <= 0:
            return 0
        # 10^11 约为 1973 年的毫秒时间戳，低于该值可视为秒级时间戳
        return ts * 1000 if ts < 100_000_000_000 else ts

    @staticmethod
    def _format_ms(ts_ms: int) -> str:
        ts_ms = DailyPinAuditor._normalize_timestamp_ms(ts_ms)
        if ts_ms <= 0:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _get_yesterday_window():
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        start = datetime.combine(yesterday, dtime.min)
        end = start + timedelta(days=1)
        return start, end

    @staticmethod
    def _get_last_week_window():
        """获取上周自然周窗口（周一 00:00 到本周一 00:00）"""
        today = datetime.now().date()
        this_week_start = today - timedelta(days=today.weekday())
        last_week_start = this_week_start - timedelta(days=7)
        start = datetime.combine(last_week_start, dtime.min)
        end = start + timedelta(days=7)
        return start, end
