"""
utils.py 单元测试

测试LRU缓存、线程安全缓存和工具函数
"""
import unittest
import threading
import time
from datetime import datetime
from utils import LRUCache, ThreadSafeLRUCache, get_timestamp_ms, extract_open_id, sanitize_log_data


class TestLRUCache(unittest.TestCase):
    """测试LRUCache类"""

    def test_basic_operations(self):
        """测试基本的get/set操作"""
        cache = LRUCache(capacity=3)

        # 测试set和get
        cache.set("key1", "value1")
        self.assertEqual(cache.get("key1"), "value1")

        # 测试默认值
        self.assertIsNone(cache.get("nonexistent"))
        self.assertEqual(cache.get("nonexistent", "default"), "default")

    def test_capacity_limit(self):
        """测试容量限制"""
        cache = LRUCache(capacity=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # 缓存已满
        self.assertEqual(len(cache), 3)

        # 添加第4个元素，应该淘汰最久未使用的key1
        cache.set("key4", "value4")
        self.assertEqual(len(cache), 3)
        self.assertIsNone(cache.get("key1"))
        self.assertEqual(cache.get("key4"), "value4")

    def test_lru_eviction(self):
        """测试LRU淘汰策略"""
        cache = LRUCache(capacity=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # 访问key1，使其成为最近使用
        cache.get("key1")

        # 添加key4，应该淘汰key2（最久未使用）
        cache.set("key4", "value4")

        self.assertEqual(cache.get("key1"), "value1")  # 仍存在
        self.assertIsNone(cache.get("key2"))  # 被淘汰
        self.assertEqual(cache.get("key3"), "value3")  # 仍存在
        self.assertEqual(cache.get("key4"), "value4")  # 新添加

    def test_update_existing_key(self):
        """测试更新已存在的键"""
        cache = LRUCache(capacity=2)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # 更新key1的值
        cache.set("key1", "new_value1")
        self.assertEqual(cache.get("key1"), "new_value1")

        # 添加key3，应该淘汰key2（因为key1刚被访问）
        cache.set("key3", "value3")
        self.assertIsNone(cache.get("key2"))

    def test_contains(self):
        """测试in操作符"""
        cache = LRUCache(capacity=2)

        cache.set("key1", "value1")

        self.assertIn("key1", cache)
        self.assertNotIn("key2", cache)

    def test_len(self):
        """测试len()函数"""
        cache = LRUCache(capacity=5)

        self.assertEqual(len(cache), 0)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        self.assertEqual(len(cache), 2)

    def test_clear(self):
        """测试清空缓存"""
        cache = LRUCache(capacity=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        self.assertEqual(len(cache), 2)

        cache.clear()

        self.assertEqual(len(cache), 0)
        self.assertIsNone(cache.get("key1"))

    def test_zero_capacity(self):
        """测试容量为0的异常情况"""
        with self.assertRaises(ValueError):
            LRUCache(capacity=0)

    def test_negative_capacity(self):
        """测试负容量的异常情况"""
        with self.assertRaises(ValueError):
            LRUCache(capacity=-1)


class TestThreadSafeLRUCache(unittest.TestCase):
    """测试ThreadSafeLRUCache类"""

    def test_basic_operations(self):
        """测试基本操作"""
        cache = ThreadSafeLRUCache(capacity=3)

        cache.set("key1", "value1")
        self.assertEqual(cache.get("key1"), "value1")

    def test_thread_safety(self):
        """测试线程安全性"""
        cache = ThreadSafeLRUCache(capacity=100)
        errors = []

        def writer_thread(start_id):
            """写入线程"""
            try:
                for i in range(start_id, start_id + 50):
                    cache.set(f"key{i}", f"value{i}")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def reader_thread():
            """读取线程"""
            try:
                for i in range(100):
                    cache.get(f"key{i}")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # 创建多个读写线程
        threads = [
            threading.Thread(target=writer_thread, args=(0,)),
            threading.Thread(target=writer_thread, args=(50,)),
            threading.Thread(target=reader_thread),
            threading.Thread(target=reader_thread)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # 不应该有任何错误
        self.assertEqual(len(errors), 0)

        # 缓存应该有数据
        self.assertGreater(len(cache), 0)


class TestUtilityFunctions(unittest.TestCase):
    """测试工具函数"""

    def test_get_timestamp_ms(self):
        """测试获取毫秒级时间戳"""
        ts = get_timestamp_ms()

        # 应该是整数
        self.assertIsInstance(ts, int)

        # 应该是13位数字（毫秒级）
        self.assertEqual(len(str(ts)), 13)

        # 应该接近当前时间
        now_ts = int(datetime.now().timestamp() * 1000)
        self.assertAlmostEqual(ts, now_ts, delta=1000)  # 误差在1秒内

    def test_extract_open_id_from_dict(self):
        """测试从字典提取open_id"""
        sender_obj = {"open_id": "ou_123456"}

        result = extract_open_id(sender_obj)

        self.assertEqual(result, "ou_123456")

    def test_extract_open_id_from_string(self):
        """测试从字符串提取open_id"""
        sender_obj = "ou_123456"

        result = extract_open_id(sender_obj)

        self.assertEqual(result, "ou_123456")

    def test_extract_open_id_from_empty_dict(self):
        """测试从空字典提取open_id"""
        sender_obj = {}

        result = extract_open_id(sender_obj)

        self.assertEqual(result, "")

    def test_extract_open_id_from_none(self):
        """测试从None提取open_id"""
        result = extract_open_id(None)

        self.assertEqual(result, "")

    def test_sanitize_log_data_dict(self):
        """测试清理日志字典中的敏感信息"""
        data = {
            "token": "abc123",
            "app_secret": "secret123",
            "name": "张三",
            "age": 25
        }

        result = sanitize_log_data(data)

        self.assertEqual(result["token"], "***")
        self.assertEqual(result["app_secret"], "***")
        self.assertEqual(result["name"], "张三")
        self.assertEqual(result["age"], 25)

    def test_sanitize_log_data_non_dict(self):
        """测试清理非字典类型的日志数据"""
        data = "some string"

        result = sanitize_log_data(data)

        self.assertEqual(result, "some string")

    def test_sanitize_log_data_case_insensitive(self):
        """测试清理敏感信息是否大小写不敏感"""
        data = {
            "Token": "abc123",
            "APP_SECRET": "secret123",
            "Authorization": "Bearer xxx"
        }

        result = sanitize_log_data(data)

        self.assertEqual(result["Token"], "***")
        self.assertEqual(result["APP_SECRET"], "***")
        self.assertEqual(result["Authorization"], "***")


if __name__ == '__main__':
    unittest.main()
