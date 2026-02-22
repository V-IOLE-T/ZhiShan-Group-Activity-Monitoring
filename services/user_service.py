"""
用户信息获取服务

统一处理飞书用户信息获取，包括：
1. 单个用户信息获取
2. 批量用户信息获取
3. 群备注优先逻辑
4. 缓存优化
"""

import os
from typing import Dict, List, Optional

import requests

from rate_limiter import with_rate_limit
from utils import ThreadSafeLRUCache


class UserService:
    """
    用户信息获取服务类

    提供静态方法获取用户信息，支持：
    - 单用户查询
    - 批量查询
    - 群备注优先
    - 线程安全缓存
    """

    # API 端点
    BASE_URL = "https://open.feishu.cn/open-apis"
    USER_INFO_URL = f"{BASE_URL}/contact/v3/users"
    BATCH_USER_INFO_URL = f"{BASE_URL}/contact/v3/users/batch_get"
    CHAT_MEMBERS_URL = f"{BASE_URL}/im/v1/chats"

    # 类级别的缓存（所有实例共享）
    _cache = ThreadSafeLRUCache(capacity=500)

    @staticmethod
    @with_rate_limit
    def get_user_info(
        user_id: str,
        auth_token: str,
        chat_id: str = None
    ) -> Optional[dict]:
        """
        获取单个用户信息

        Args:
            user_id: 用户 ID
            auth_token: 认证 Token
            chat_id: 群组 ID（可选，提供时优先获取群备注）

        Returns:
            用户信息字典，包含：
            - user_id: 用户 ID
            - name: 用户名称（群备注优先）
            - avatar_url: 头像链接
            失败返回 None

        Example:
            >>> info = UserService.get_user_info("ou_xxx", "Bearer token", "oc_xxx")
            >>> if info:
            ...     print(f"用户: {info['name']}")
        """
        if not user_id:
            return None

        # 检查缓存
        cache_key = f"user:{user_id}:{chat_id or 'default'}"
        if cache_key in UserService._cache:
            return UserService._cache.get(cache_key)

        headers = {
            "Authorization": auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}",
        }

        # 如果提供了 chat_id，优先获取群备注
        if chat_id:
            user_info = UserService._get_chat_member_info(user_id, chat_id, headers)
            if user_info:
                UserService._cache.set(cache_key, user_info)
                return user_info

        # 降级：获取用户基本信息
        url = f"{UserService.USER_INFO_URL}/{user_id}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()

            if data.get("code") == 0:
                user_data = data.get("data", {}).get("user", {})
                user_info = {
                    "user_id": user_id,
                    "name": user_data.get("name", user_id),
                    "avatar_url": user_data.get("avatar", {}).get("avatar_240")
                }
                UserService._cache.set(cache_key, user_info)
                return user_info
            else:
                print(f"  > [UserService] ⚠️ 获取用户信息失败: {data.get('msg')}")
                return None

        except Exception as e:
            print(f"  > [UserService] ❌ 获取用户信息异常: {e}")
            return None

    @staticmethod
    def _get_chat_member_info(user_id: str, chat_id: str, headers: dict) -> Optional[dict]:
        """
        获取群成员信息（群备注优先）

        Args:
            user_id: 用户 ID
            chat_id: 群组 ID
            headers: 请求头

        Returns:
            用户信息字典，失败返回 None
        """
        url = f"{UserService.CHAT_MEMBERS_URL}/{chat_id}/members"
        params = {
            "member_id_type": "user_id",
            "member_ids": user_id
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            data = response.json()

            if data.get("code") == 0:
                items = data.get("data", {}).get("items", [])
                if items:
                    member = items[0]
                    return {
                        "user_id": user_id,
                        "name": member.get("name", user_id),
                        "avatar_url": None  # 群成员接口不返回头像
                    }
        except Exception as e:
            print(f"  > [UserService] ⚠️ 获取群成员信息失败: {e}")

        return None

    @staticmethod
    @with_rate_limit
    def get_batch_user_info(
        user_ids: List[str],
        auth_token: str,
        chat_id: str = None
    ) -> Dict[str, dict]:
        """
        批量获取用户信息

        Args:
            user_ids: 用户 ID 列表
            auth_token: 认证 Token
            chat_id: 群组 ID（可选，提供时优先获取群备注）

        Returns:
            用户信息字典，key 为 user_id，value 为用户信息字典

        Example:
            >>> users = UserService.get_batch_user_info(["ou_xxx", "ou_yyy"], "Bearer token")
            >>> for user_id, info in users.items():
            ...     print(f"{user_id}: {info['name']}")
        """
        if not user_ids:
            return {}

        result = {}

        # 如果提供了 chat_id，优先使用群成员接口
        if chat_id:
            result = UserService._batch_get_chat_members(user_ids, chat_id, auth_token)

        # 对于未获取到的用户，使用批量用户信息接口
        remaining_ids = [uid for uid in user_ids if uid not in result]
        if remaining_ids:
            result.update(UserService._batch_get_user_info(remaining_ids, auth_token))

        return result

    @staticmethod
    def _batch_get_chat_members(
        user_ids: List[str],
        chat_id: str,
        auth_token: str
    ) -> Dict[str, dict]:
        """批量获取群成员信息"""
        headers = {
            "Authorization": auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}",
        }

        # 群成员接口每次最多查询 50 个
        result = {}
        for i in range(0, len(user_ids), 50):
            batch_ids = user_ids[i:i + 50]

            url = f"{UserService.CHAT_MEMBERS_URL}/{chat_id}/members"
            params = {
                "member_id_type": "user_id",
                "member_ids": ",".join(batch_ids)
            }

            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                data = response.json()

                if data.get("code") == 0:
                    items = data.get("data", {}).get("items", [])
                    for item in items:
                        member_id = item.get("member_id", {}).get("user_id")
                        if member_id:
                            result[member_id] = {
                                "user_id": member_id,
                                "name": item.get("name", member_id),
                                "avatar_url": None
                            }
            except Exception as e:
                print(f"  > [UserService] ⚠️ 批量获取群成员失败: {e}")

        return result

    @staticmethod
    def _batch_get_user_info(user_ids: List[str], auth_token: str) -> Dict[str, dict]:
        """批量获取用户基本信息"""
        headers = {
            "Authorization": auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}",
        }

        result = {}

        # 批量接口每次最多查询 50 个
        for i in range(0, len(user_ids), 50):
            batch_ids = user_ids[i:i + 50]

            payload = {
                "user_ids": batch_ids,
                "include_resigned": True
            }

            try:
                response = requests.post(
                    UserService.BATCH_USER_INFO_URL,
                    headers=headers,
                    json=payload,
                    timeout=10
                )
                data = response.json()

                if data.get("code") == 0:
                    user_list = data.get("data", {}).get("user_list", [])
                    for user_data in user_list:
                        user_id = user_data.get("user_id") or user_data.get("open_id")
                        if user_id:
                            result[user_id] = {
                                "user_id": user_id,
                                "name": user_data.get("name", user_id),
                                "avatar_url": user_data.get("avatar", {}).get("avatar_240")
                            }
            except Exception as e:
                print(f"  > [UserService] ⚠️ 批量获取用户信息失败: {e}")

        return result

    @staticmethod
    def clear_cache():
        """清空缓存"""
        UserService._cache.clear()
        print("  > [UserService] ✅ 用户缓存已清空")

    @staticmethod
    def get_cache_size() -> int:
        """获取缓存大小"""
        return len(UserService._cache)
