"""
工具函数和通用类
包含项目中复用的工具类和辅助函数
"""
import threading
from collections import OrderedDict
from typing import Any, Optional
from datetime import datetime


class LRUCache:
    """
    LRU(Least Recently Used)缓存实现

    自动淘汰最久未使用的项，防止内存无限增长

    Attributes:
        capacity: 缓存容量上限
        cache: 有序字典存储缓存数据

    Example:
        >>> cache = LRUCache(capacity=100)
        >>> cache.set("key1", "value1")
        >>> cache.get("key1")
        'value1'
    """

    def __init__(self, capacity: int = 500):
        """
        初始化LRU缓存

        Args:
            capacity: 缓存容量，默认500
        """
        if capacity <= 0:
            raise ValueError("缓存容量必须大于0")
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取缓存值，如果存在则移到末尾(标记为最近使用)

        Args:
            key: 缓存键
            default: 键不存在时的默认返回值

        Returns:
            缓存值或默认值
        """
        if key in self.cache:
            # 移到最后（最近使用）
            self.cache.move_to_end(key)
            return self.cache[key]
        return default

    def set(self, key: str, value: Any) -> None:
        """
        设置缓存值

        如果键已存在，移到末尾
        如果缓存已满，删除最久未使用的项

        Args:
            key: 缓存键
            value: 缓存值
        """
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        # 超出容量时删除最久未使用的项
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def __contains__(self, key: str) -> bool:
        """支持 in 操作符"""
        return key in self.cache

    def __len__(self) -> int:
        """返回缓存当前大小"""
        return len(self.cache)

    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()


class ThreadSafeLRUCache(LRUCache):
    """
    线程安全的LRU缓存

    在多线程环境下使用，所有操作都加锁保护

    Example:
        >>> cache = ThreadSafeLRUCache(capacity=100)
        >>> cache.set("key1", "value1")  # 线程安全
        >>> cache.get("key1")
        'value1'
    """

    def __init__(self, capacity: int = 500):
        """
        初始化线程安全的LRU缓存

        Args:
            capacity: 缓存容量，默认500
        """
        super().__init__(capacity)
        self._lock = threading.Lock()

    def get(self, key: str, default: Any = None) -> Any:
        """
        线程安全地获取缓存值

        Args:
            key: 缓存键
            default: 键不存在时的默认返回值

        Returns:
            缓存值或默认值
        """
        with self._lock:
            return super().get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        线程安全地设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
        """
        with self._lock:
            super().set(key, value)

    def __contains__(self, key: str) -> bool:
        """线程安全的 in 操作"""
        with self._lock:
            return super().__contains__(key)

    def __len__(self) -> int:
        """线程安全地返回缓存大小"""
        with self._lock:
            return super().__len__()

    def clear(self) -> None:
        """线程安全地清空缓存"""
        with self._lock:
            super().clear()


def get_timestamp_ms() -> int:
    """
    获取当前时间戳(毫秒)

    Returns:
        当前时间的毫秒级时间戳

    Example:
        >>> ts = get_timestamp_ms()
        >>> ts
        1705308000000
    """
    return int(datetime.now().timestamp() * 1000)


def extract_open_id(sender_id_obj: Any) -> str:
    """
    从sender.id提取open_id

    兼容处理sender.id可能是字符串或字典的情况

    Args:
        sender_id_obj: sender.id对象，可能是字符串或字典

    Returns:
        提取的open_id，如果无法提取则返回空字符串

    Example:
        >>> extract_open_id({"open_id": "ou_123"})
        'ou_123'
        >>> extract_open_id("ou_123")
        'ou_123'
        >>> extract_open_id(None)
        ''
    """
    if isinstance(sender_id_obj, dict):
        return sender_id_obj.get('open_id', '')
    elif isinstance(sender_id_obj, str):
        return sender_id_obj
    return ''


def sanitize_log_data(data: Any) -> Any:
    """
    清理日志中的敏感信息

    将token、secret、password等敏感字段替换为***

    Args:
        data: 要清理的数据，可以是字典或其他类型

    Returns:
        清理后的数据

    Example:
        >>> sanitize_log_data({"token": "abc123", "name": "张三"})
        {'token': '***', 'name': '张三'}
    """
    sensitive_keys = ['token', 'secret', 'password', 'authorization', 'app_secret']

    if isinstance(data, dict):
        return {
            k: '***' if any(s in k.lower() for s in sensitive_keys) else v
            for k, v in data.items()
        }
    return data


def upload_file_to_bitable(
    file_content: bytes,
    file_name: str,
    app_token: str,
    auth_token: str,
    upload_url: str = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
) -> Optional[Dict[str, Any]]:
    """
    上传文件到飞书多维表格

    统一的文件上传逻辑，避免代码重复

    Args:
        file_content: 文件内容（字节）
        file_name: 文件名
        app_token: 多维表格的app_token
        auth_token: 认证token
        upload_url: 上传API地址，默认为飞书标准上传接口

    Returns:
        成功时返回包含file_token的字典:
        {
            "file_token": "xxx",
            "name": "file.txt",
            "size": 1024,
            "type": "file"
        }
        失败时返回None

    Example:
        >>> from auth import FeishuAuth
        >>> auth = FeishuAuth()
        >>> result = upload_file_to_bitable(
        ...     file_content=b"Hello",
        ...     file_name="test.txt",
        ...     app_token="bascnxxx",
        ...     auth_token=auth.get_tenant_access_token()
        ... )
    """
    import requests

    form_data = {
        'file_name': file_name,
        'parent_type': 'bitable_file',
        'parent_node': app_token,
        'size': str(len(file_content))
    }

    files = {
        'file': (file_name, file_content)
    }

    upload_headers = {
        "Authorization": f"Bearer {auth_token}"
    }

    try:
        response = requests.post(
            upload_url,
            headers=upload_headers,
            data=form_data,
            files=files,
            timeout=60
        )

        if response.status_code != 200:
            print(f"  > [文件上传] ❌ HTTP错误: {response.status_code}")
            print(f"  > [文件上传] 响应: {response.text[:200]}")
            return None

        try:
            result = response.json()
        except Exception as e:
            print(f"  > [文件上传] ❌ JSON解析失败: {e}")
            print(f"  > [文件上传] 原始响应: {response.text[:200]}")
            return None

        if result.get('code') == 0:
            data_obj = result.get('data', {})
            file_token = data_obj.get('file_token')

            if file_token:
                print(f"  > [文件上传] ✅ 文件已上传: {file_name} -> {file_token}")
                return {
                    "file_token": file_token,
                    "name": file_name,
                    "size": len(file_content),
                    "type": "file"
                }
            else:
                print(f"  > [文件上传] ❌ 响应中未找到file_token: {result}")
                return None
        else:
            print(f"  > [文件上传] ❌ 上传失败: {result}")
            return None

    except requests.exceptions.Timeout:
        print(f"  > [文件上传] ❌ 上传超时: {file_name}")
        return None
    except Exception as e:
        print(f"  > [文件上传] ❌ 上传异常: {e}")
        return None
