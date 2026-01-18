"""
消息采集模块

负责从飞书API获取群聊消息和用户信息
支持分页、时间过滤和自动限流
"""

import requests
import time
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
from config import MAX_MESSAGES_PER_FETCH, MAX_PAGES_PER_FETCH, PAGE_SLEEP_TIME, API_TIMEOUT
from rate_limiter import with_rate_limit

load_dotenv()


class MessageCollector:
    """
    消息采集器

    从飞书API获取群聊消息列表和用户信息

    Attributes:
        auth: FeishuAuth认证实例
        chat_id: 要监控的群聊ID

    Example:
        >>> from auth import FeishuAuth
        >>> auth = FeishuAuth()
        >>> collector = MessageCollector(auth)
        >>> messages = collector.get_messages(hours=1)
        >>> print(f"采集到 {len(messages)} 条消息")
    """

    def __init__(self, auth) -> None:
        """
        初始化消息采集器

        Args:
            auth: FeishuAuth认证实例

        Raises:
            ValueError: 当CHAT_ID未配置时（在首次调用API时抛出）
        """
        self.auth = auth
        self.chat_id: Optional[str] = os.getenv("CHAT_ID")

    @with_rate_limit
    def get_messages(self, hours: int = 1) -> List[Dict[str, Any]]:
        """
        获取指定时间范围内的群聊消息

        支持分页获取，自动过滤时间范围，防止无限循环和内存溢出

        Args:
            hours: 获取最近N小时的消息，默认1小时

        Returns:
            消息列表，每条消息为字典格式

        Note:
            - 最多获取MAX_MESSAGES_PER_FETCH条消息（默认5000条）
            - 最多翻MAX_PAGES_PER_FETCH页（默认100页）
            - 自动应用速率限制

        Example:
            >>> collector = MessageCollector(auth)
            >>> messages = collector.get_messages(hours=24)
            >>> for msg in messages:
            ...     print(msg.get('message_id'))
        """
        url = "https://open.feishu.cn/open-apis/im/v1/messages"

        # 计算时间阈值（毫秒）
        time_threshold = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)

        all_messages = []
        page_token = None
        page_count = 0

        while True:
            page_count += 1

            # ⚡ 保护1: 最大页数限制
            if page_count > MAX_PAGES_PER_FETCH:
                print(f"⚠️ 已达到最大页数限制({MAX_PAGES_PER_FETCH})，停止获取")
                break

            # ⚡ 保护2: 最大消息数限制
            if len(all_messages) >= MAX_MESSAGES_PER_FETCH:
                print(f"⚠️ 已达到消息数量限制({MAX_MESSAGES_PER_FETCH})，停止获取")
                break

            # 不使用 start_time 和 end_time，直接获取最新消息
            params = {"container_id_type": "chat", "container_id": self.chat_id, "page_size": 50}

            if page_token:
                params["page_token"] = page_token

            try:
                response = requests.get(
                    url, headers=self.auth.get_headers(), params=params, timeout=API_TIMEOUT
                )
                data = response.json()

                if data.get("code") != 0:
                    print(f"❌ 获取消息失败: {data}")
                    break

                messages = data.get("data", {}).get("items", [])

                # 在代码层面过滤时间范围
                for msg in messages:
                    create_time = msg.get("create_time", 0)
                    if isinstance(create_time, str):
                        create_time = int(create_time)

                    # 只保留指定时间范围内的消息
                    if create_time >= time_threshold:
                        all_messages.append(msg)
                        # 再次检查消息数限制
                        if len(all_messages) >= MAX_MESSAGES_PER_FETCH:
                            break

                # 如果没有更多消息，或者已经获取到足够旧的消息，停止翻页
                if not data.get("data", {}).get("has_more"):
                    break

                # 检查最后一条消息是否已经超出时间范围
                if messages:
                    last_msg_time = messages[-1].get("create_time", 0)
                    if isinstance(last_msg_time, str):
                        last_msg_time = int(last_msg_time)
                    if last_msg_time < time_threshold:
                        break

                page_token = data.get("data", {}).get("page_token")
                time.sleep(PAGE_SLEEP_TIME)  # 使用配置文件中的延迟时间

            except requests.exceptions.Timeout:
                print(f"⚠️ 第{page_count}页请求超时，停止获取")
                break
            except Exception as e:
                print(f"❌ 获取消息出错: {e}")
                break

        print(f"✅ 采集到 {len(all_messages)} 条消息（共{page_count}页）")
        return all_messages

    @with_rate_limit
    def get_user_names(self, user_ids: List[str]) -> Dict[str, str]:
        """
        获取群聊成员在群里的昵称（备注名）

        批量获取用户在群内的显示名称，优先返回群内备注名

        Args:
            user_ids: 用户open_id列表

        Returns:
            用户ID到昵称的映射字典 {open_id: name}

        Note:
            - 如果用户不在群内，该用户不会出现在结果中
            - 优先使用群内备注名，没有则使用真实姓名
            - 自动分页获取所有群成员

        Example:
            >>> collector = MessageCollector(auth)
            >>> user_ids = ['ou_123', 'ou_456']
            >>> names = collector.get_user_names(user_ids)
            >>> print(names)
            {'ou_123': '张三', 'ou_456': '李四'}
        """
        if not user_ids:
            return {}

        url = f"https://open.feishu.cn/open-apis/im/v1/chats/{self.chat_id}/members"
        user_names = {}
        page_token = None

        print("正在获取群成员备注...")

        while True:
            params = {"member_id_type": "open_id", "page_size": 100}
            if page_token:
                params["page_token"] = page_token

            try:
                response = requests.get(
                    url, headers=self.auth.get_headers(), params=params, timeout=10
                )
                data = response.json()

                if data.get("code") == 0:
                    data_obj = data.get("data") or {}
                    items = data_obj.get("items") or []
                    for member in items:
                        # 优先使用在群里的备注名 (name)，如果没有则使用真实姓名
                        user_names[member.get("member_id")] = member.get("name", "")

                    if not data_obj.get("has_more"):
                        break
                    page_token = data_obj.get("page_token")
                else:
                    print(f"获取群成员列表失败: {data}")
                    break
            except Exception as e:
                print(f"请求群成员信息出错: {e}")
                break

        return user_names

    @with_rate_limit
    def get_message_sender(self, message_id: str) -> Optional[str]:
        """
        获取指定消息的发送者ID

        根据消息ID查询消息详情，提取发送者open_id

        Args:
            message_id: 消息ID

        Returns:
            发送者的open_id，如果获取失败返回None

        Note:
            - 需要im:message权限
            - 消息可能已被删除或撤回
            - 自动应用速率限制

        Example:
            >>> collector = MessageCollector(auth)
            >>> sender_id = collector.get_message_sender('om_xxx')
            >>> print(sender_id)
            'ou_123'
        """
        if not message_id:
            return None

        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
        try:
            response = requests.get(url, headers=self.auth.get_headers(), timeout=10)
            data = response.json()
            if data.get("code") == 0:
                data_obj = data.get("data") or {}
                items = data_obj.get("items") or []
                if not items:
                    print(f"未找到消息 {message_id} 的详情")
                    return None

                sender = items[0].get("sender", {})
                sender_id_obj = sender.get("id", {})
                if isinstance(sender_id_obj, dict):
                    return sender_id_obj.get("open_id")
                return sender_id_obj
            else:
                print(f"获取消息详情失败: {data}")
        except Exception as e:
            print(f"请求消息详情出错: {e}")
        return None

    @with_rate_limit
    def get_message_detail(self, message_id: str) -> Optional[Dict[str, Any]]:
        """获取单条消息详情"""
        if not message_id:
            return None
            
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
        
        try:
            response = requests.get(url, headers=self.auth.get_headers(), timeout=API_TIMEOUT)
            data = response.json()
            if data.get("code") == 0:
                items = data.get("data", {}).get("items", [])
                if items:
                    return items[0] # API 返回 items 列表
            else:
                print(f"⚠️ 获取消息详情失败: {data}")
            return None
        except Exception as e:
            print(f"❌ 获取消息详情异常: {e}")
            return None
