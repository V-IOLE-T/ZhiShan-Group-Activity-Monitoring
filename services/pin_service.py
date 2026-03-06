"""
Pin 处理服务

统一处理飞书 Pin 消息相关操作，包括：
1. 获取 Pin 消息列表（支持分页）
2. 获取消息详情（含附件）
3. 附件转存
4. Bitable 归档
5. 用户信息获取（带缓存）
6. 去重机制
7. 精华文档写入

此服务整合了以下重复代码：
- pin_monitor.py 中的 Pin 处理逻辑
- pin_daily_audit.py 中的 Pin 审计逻辑
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

import requests

from rate_limiter import with_rate_limit
from utils import ThreadSafeLRUCache
from services.file_upload_service import FileUploadService


class PinService:
    """
    Pin 消息处理服务类

    提供静态方法处理 Pin 消息的获取、处理和归档
    """

    # API 端点
    BASE_URL = "https://open.feishu.cn/open-apis"
    PINS_URL = f"{BASE_URL}/im/v1/pins"
    MESSAGE_URL = f"{BASE_URL}/im/v1/messages"
    MESSAGES_SEND_URL = f"{BASE_URL}/im/v1/messages"

    # 去重记录文件
    PROCESSED_FILE = Path(__file__).parent.parent / ".processed_daily_pins.txt"
    MAX_PIN_PAGE_SIZE = 50

    # 类级别的缓存（所有实例共享）
    _user_name_cache = ThreadSafeLRUCache(capacity=500)
    _pin_details_cache = ThreadSafeLRUCache(capacity=200)

    @staticmethod
    @with_rate_limit
    def get_pinned_messages(chat_id: str, auth_token: str, page_size: int = 50) -> List[dict]:
        """
        获取群内所有 Pin 消息列表（支持分页）

        Args:
            chat_id: 群组 ID
            auth_token: 认证 Token
            page_size: 每页数量（默认100）

        Returns:
            Pin 消息列表，每个元素包含 message_id、operator_id、create_time

        Example:
            >>> pins = PinService.get_pinned_messages("oc_xxx", "Bearer token")
            >>> for pin in pins:
            ...     print(f"Message: {pin['message_id']}")
        """
        headers = {
            "Authorization": auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

        all_pins = []
        page_token = None

        while True:
            params = {
                "chat_id": chat_id,
                "page_size": min(page_size, PinService.MAX_PIN_PAGE_SIZE)
            }

            if page_token:
                params["page_token"] = page_token

            try:
                response = requests.get(
                    PinService.PINS_URL,
                    headers=headers,
                    params=params,
                    timeout=10
                )

                if response.status_code != 200:
                    print(f"  > [PinService] ❌ HTTP错误: {response.status_code}")
                    break

                data = response.json()

                if data.get("code") == 0:
                    items = data.get("data", {}).get("items", [])
                    all_pins.extend(items)

                    # 检查是否还有更多页
                    page_token = data.get("data", {}).get("page_token")
                    if not page_token:
                        break
                else:
                    print(f"  > [PinService] ❌ API返回错误: {data.get('msg')}")
                    break

            except requests.exceptions.Timeout:
                print(f"  > [PinService] ❌ 请求超时")
                break
            except requests.exceptions.RequestException as e:
                print(f"  > [PinService] ❌ 请求异常: {e}")
                break

        print(f"  > [PinService] 获取到 {len(all_pins)} 条 Pin 消息")
        return all_pins

    @staticmethod
    @with_rate_limit
    def get_message_detail(message_id: str, auth_token: str) -> Optional[dict]:
        """
        获取消息详情（含附件）

        Args:
            message_id: 消息 ID
            auth_token: 认证 Token

        Returns:
            消息详情字典，包含：
            - sender_id: 发送者 ID
            - message_type: 消息类型
            - content: 纯文本内容
            - raw_content: 原始 JSON 内容
            - create_time: 创建时间
            - image_keys: 图片 keys 列表
            - file_key: 文件 key
            - file_name: 文件名
            - image_key: 图片 key
        """
        # 检查缓存
        if message_id in PinService._pin_details_cache:
            return PinService._pin_details_cache.get(message_id)

        headers = {
            "Authorization": auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(
                f"{PinService.MESSAGE_URL}/{message_id}",
                headers=headers,
                timeout=10
            )

            data = response.json()

            if data.get("code") == 0:
                message_data = data.get("data", {}).get("items", [{}])[0]
                msg_type = message_data.get("msg_type")
                content_str = message_data.get("body", {}).get("content", "")

                # 提取纯文本和图片 keys
                text_content, image_keys = PinService._extract_text_and_images(content_str)

                # 解析 content 获取文件信息
                try:
                    content_obj = (
                        json.loads(content_str) if isinstance(content_str, str) else content_str
                    )
                except (json.JSONDecodeError, ValueError):
                    content_obj = {}

                details = {
                    "sender_id": message_data.get("sender", {}).get("id"),
                    "message_type": msg_type,
                    "content": text_content,
                    "raw_content": content_str,
                    "create_time": message_data.get("create_time"),
                    "chat_id": message_data.get("chat_id"),
                    "image_keys": image_keys,
                    "file_key": content_obj.get("file_key"),
                    "file_name": content_obj.get("file_name"),
                    "image_key": content_obj.get("image_key"),
                }

                # 存入缓存
                PinService._pin_details_cache.set(message_id, details)
                return details
            else:
                print(f"  > [PinService] ❌ 获取消息详情失败: {data.get('msg')}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"  > [PinService] ❌ 获取消息详情异常: {e}")
            return None

    @staticmethod
    def _extract_text_and_images(content_str: str) -> tuple:
        """
        从内容中提取纯文本和图片 keys

        Args:
            content_str: JSON 格式的内容字符串

        Returns:
            (纯文本内容, 图片 keys 列表)
        """
        try:
            content_obj = json.loads(content_str) if isinstance(content_str, str) else content_str
        except (json.JSONDecodeError, ValueError):
            return content_str, []

        text_parts = []
        image_keys = []

        def traverse_text(elements):
            """递归遍历文本元素"""
            if isinstance(elements, list):
                for elem in elements:
                    traverse_text(elem)
            elif isinstance(elements, dict):
                tag = elements.get("tag")
                if tag == "text":
                    text_parts.append(elements.get("text", ""))
                elif tag == "img":
                    image_key = elements.get("image_key")
                    if image_key:
                        image_keys.append(image_key)
                # 递归处理子元素
                for key, value in elements.items():
                    if key in ["text", "elements", "mention"] and isinstance(value, list):
                        traverse_text(value)

        if isinstance(content_obj, list):
            traverse_text(content_obj)
        elif isinstance(content_obj, dict):
            elements = content_obj.get("text") or content_obj.get("elements", [])
            traverse_text(elements)

        return "".join(text_parts).strip(), list(set(image_keys))

    @staticmethod
    def get_user_name(user_id: str, chat_id: str, auth_token: str) -> str:
        """
        获取用户昵称（带缓存，群备注优先）

        Args:
            user_id: 用户 ID
            chat_id: 群组 ID
            auth_token: 认证 Token

        Returns:
            用户昵称，失败返回用户 ID
        """
        if not user_id:
            return user_id

        # 检查缓存
        if user_id in PinService._user_name_cache:
            return PinService._user_name_cache.get(user_id)

        headers = {
            "Authorization": auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}",
        }

        try:
            # 获取群成员信息（群备注）
            url = f"{PinService.BASE_URL}/im/v1/chats/{chat_id}/members"
            params = {"member_id_type": "user_id", "member_ids": user_id}

            response = requests.get(url, headers=headers, params=params, timeout=10)
            data = response.json()

            if data.get("code") == 0:
                items = data.get("data", {}).get("items", [])
                if items:
                    name = items[0].get("name") or user_id
                    PinService._user_name_cache.set(user_id, name)
                    return name

        except Exception as e:
            print(f"  > [PinService] ⚠️ 获取群成员信息失败: {e}")

        # 缓存并返回 user_id
        PinService._user_name_cache.set(user_id, user_id)
        return user_id

    @staticmethod
    def download_and_upload_resource(
        message_id: str,
        resource_key: str,
        resource_type: str,
        file_name: str,
        auth_token: str,
        app_token: str
    ) -> Optional[dict]:
        """
        下载并上传资源到 Bitable

        Args:
            message_id: 消息 ID（用于日志）
            resource_key: 资源 key（image_key 或 file_key）
            resource_type: 资源类型（"image" 或 "file"）
            file_name: 文件名
            auth_token: 认证 Token
            app_token: Bitable 应用 Token

        Returns:
            成功返回 {"file_token": "xxx", "name": "xxx", "size": xxx, "type": "xxx"}
            失败返回 None
        """
        # 检查附件大小限制（10MB）
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

        headers = {
            "Authorization": auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}",
        }

        # 下载资源
        download_url = f"{PinService.BASE_URL}/im/v1/resources/{resource_key}"
        if resource_type == "file":
            download_url = f"{PinService.BASE_URL}/im/v1/files/{resource_key}/download"

        try:
            print(f"  > [PinService] 下载{resource_type}: {file_name}")
            response = requests.get(download_url, headers=headers, stream=True, timeout=30)

            if response.status_code != 200:
                print(f"  > [PinService] ❌ 下载失败({message_id}): HTTP {response.status_code}")
                return None

            # 检查文件大小
            file_size = int(response.headers.get("content-length", 0))
            if file_size > MAX_FILE_SIZE:
                print(f"  > [PinService] ⚠️ 附件过大({message_id}): {file_size / 1024 / 1024:.1f}MB")
                return None

            file_data = response.content

            # 上传到 Bitable
            result = FileUploadService.upload_to_bitable(
                file_data=file_data,
                app_token=app_token,
                table_id="",  # 不需要 table_id
                auth_token=auth_token,
                file_name=file_name
            )

            if result:
                print(f"  > [PinService] ✅ 附件转存成功: {file_name}")
            return result

        except requests.exceptions.Timeout:
            print(f"  > [PinService] ⚠️ 下载超时({message_id})")
            return None
        except requests.exceptions.RequestException as e:
            print(f"  > [PinService] ⚠️ 下载异常({message_id}): {e}")
            return None

    @staticmethod
    def archive_to_bitable(pin_info: dict, storage, app_token: str, auth_token: str) -> bool:
        """
        归档 Pin 消息到 Bitable

        Args:
            pin_info: Pin 信息字典
            storage: Storage 实例（用于调用归档方法）
            app_token: Bitable 应用 Token
            auth_token: 认证 Token

        Returns:
            成功返回 True，失败返回 False
        """
        pin_table_id = os.getenv("PIN_TABLE_ID")
        if not pin_table_id:
            print("  > [PinService] ⚠️ PIN_TABLE_ID 未配置，跳过 Bitable 归档")
            return False

        # 收集附件
        message_id = pin_info.get("message_id")
        file_tokens = []

        for image_key in pin_info.get("image_keys", []):
            token = PinService.download_and_upload_resource(
                message_id, image_key, "image", f"{image_key}.png", auth_token, app_token
            )
            if token:
                file_tokens.append(token)

        if pin_info.get("message_type") == "image" and pin_info.get("image_key"):
            token = PinService.download_and_upload_resource(
                message_id, pin_info["image_key"], "image", f"{pin_info['image_key']}.png", auth_token, app_token
            )
            if token:
                file_tokens.append(token)

        if pin_info.get("message_type") == "file" and pin_info.get("file_key"):
            token = PinService.download_and_upload_resource(
                message_id, pin_info["file_key"], "file", pin_info.get("file_name", "file"), auth_token, app_token
            )
            if token:
                file_tokens.append(token)

        pin_info["file_tokens"] = file_tokens

        # 调用 storage 的归档方法
        if hasattr(storage, "archive_pin_message"):
            return storage.archive_pin_message(pin_info)

        return False

    @staticmethod
    def increment_pin_count(user_id: str, user_name: str, storage) -> bool:
        """
        增加用户的被加精次数

        Args:
            user_id: 用户 ID
            user_name: 用户名称
            storage: Storage 实例

        Returns:
            成功返回 True，失败返回 False
        """
        if hasattr(storage, "increment_pin_count"):
            return storage.increment_pin_count(user_id, user_name)
        return False

    @staticmethod
    def write_to_essence_doc(pin_info: dict, converter, docx_storage, essence_doc_token: str) -> bool:
        """
        写入精华文档

        Args:
            pin_info: Pin 信息字典
            converter: MessageToDocxConverter 实例
            docx_storage: DocxStorage 实例
            essence_doc_token: 精华文档 Token

        Returns:
            成功返回 True，失败返回 False
        """
        if not essence_doc_token:
            print("  > [PinService] ⚠️ ESSENCE_DOC_TOKEN 未配置，跳过精华文档写入")
            return False

        if not converter or not docx_storage:
            print("  > [PinService] ⚠️ converter 或 docx_storage 未配置，跳过精华文档写入")
            return False

        try:
            blocks = converter.convert(
                pin_info.get("raw_content", ""),
                pin_info.get("message_id"),
                essence_doc_token,
                sender_name=pin_info.get("sender_name"),
                send_time=pin_info.get("create_time"),
            )
            docx_storage.add_blocks(essence_doc_token, blocks)
            print(f"  > [PinService] ✅ 已写入精华文档")
            return True
        except Exception as e:
            print(f"  > [PinService] ⚠️ 精华文档写入失败: {e}")
            return False

    @staticmethod
    def load_processed_ids() -> Set[str]:
        """
        加载已处理的 Pin 消息 ID 集合

        Returns:
            已处理的消息 ID 集合
        """
        if not PinService.PROCESSED_FILE.exists():
            return set()

        try:
            with open(PinService.PROCESSED_FILE, "r", encoding="utf-8") as f:
                return {line.strip() for line in f if line.strip()}
        except Exception as e:
            print(f"  > [PinService] ⚠️ 读取已处理记录失败: {e}")
            return set()

    @staticmethod
    def save_processed_ids(processed_ids: Set[str]) -> bool:
        """
        保存已处理的 Pin 消息 ID 集合

        Args:
            processed_ids: 已处理的消息 ID 集合

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            with open(PinService.PROCESSED_FILE, "w", encoding="utf-8") as f:
                for msg_id in processed_ids:
                    f.write(f"{msg_id}\n")
            return True
        except Exception as e:
            print(f"  > [PinService] ⚠️ 保存处理记录失败: {e}")
            return False

    @staticmethod
    def is_processed(message_id: str, processed_ids: Set[str]) -> bool:
        """
        检查消息是否已处理

        Args:
            message_id: 消息 ID
            processed_ids: 已处理的消息 ID 集合

        Returns:
            已处理返回 True，否则返回 False
        """
        return message_id in processed_ids

    @staticmethod
    def extract_user_id(operator_id: Any) -> Optional[str]:
        """
        从 operator_id 提取用户 ID

        Args:
            operator_id: 可能是字符串或字典格式

        Returns:
            用户 ID，无法解析返回 None

        Example:
            >>> PinService.extract_user_id("ou_xxx")
            'ou_xxx'
            >>> PinService.extract_user_id({"user_id": "ou_xxx"})
            'ou_xxx'
        """
        if isinstance(operator_id, str):
            return operator_id
        elif isinstance(operator_id, dict):
            return operator_id.get("user_id") or operator_id.get("open_id")
        return None

    @staticmethod
    def format_timestamp_ms(timestamp_ms: int) -> str:
        """
        格式化毫秒时间戳

        Args:
            timestamp_ms: 毫秒时间戳

        Returns:
            格式化的时间字符串 "YYYY-MM-DD HH:MM:SS"
        """
        if not timestamp_ms:
            return ""

        try:
            dt = datetime.fromtimestamp(timestamp_ms / 1000)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError):
            return ""

    @staticmethod
    def safe_int(value: Any, default: int = 0) -> int:
        """
        安全转换为整数

        Args:
            value: 要转换的值
            default: 转换失败时的默认值

        Returns:
            整数值
        """
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default
