"""
calculator.py 单元测试

测试消息指标计算器的各项功能
"""

import unittest
import json
from calculator import MetricsCalculator


class TestMetricsCalculator(unittest.TestCase):
    """测试MetricsCalculator类"""

    def test_initialization(self):
        """测试初始化"""
        messages = [{"message_id": "msg1"}]
        user_names = {"user1": "Alice"}

        calc = MetricsCalculator(messages, user_names)

        self.assertEqual(calc.messages, messages)
        self.assertEqual(calc.user_names, user_names)
        self.assertEqual(calc.msg_sender_map, {})

    def test_initialization_without_user_names(self):
        """测试不提供user_names时使用空字典"""
        messages = []
        calc = MetricsCalculator(messages)

        self.assertEqual(calc.user_names, {})

    def test_basic_message_count(self):
        """测试基本的消息计数"""
        messages = [
            {
                "message_id": "msg1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "Hello"}'},
            },
            {
                "message_id": "msg2",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "World"}'},
            },
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        self.assertEqual(metrics["user1"]["message_count"], 2)

    def test_char_count(self):
        """测试字符计数"""
        messages = [
            {
                "message_id": "msg1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "Hello World"}'},
            }
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        # "Hello World" = 11 characters
        self.assertEqual(metrics["user1"]["char_count"], 11)

    def test_char_count_with_mentions_removed(self):
        """测试字符计数会移除@标签"""
        messages = [
            {
                "message_id": "msg1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "Hello @user2 World"}'},
            }
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        # "Hello  World" (移除@user2后) ≈ 12个字符
        self.assertLess(metrics["user1"]["char_count"], 20)

    def test_reply_received(self):
        """测试回复计数"""
        messages = [
            {
                "message_id": "msg1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "Original message"}'},
            },
            {
                "message_id": "msg2",
                "sender": {"id": "user2"},
                "parent_id": "msg1",
                "body": {"content": '{"text": "Reply"}'},
            },
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        # user1发的msg1收到1条回复
        self.assertEqual(metrics["user1"]["reply_received"], 1)
        self.assertEqual(metrics["user2"]["reply_received"], 0)

    def test_mention_received(self):
        """测试@提及计数"""
        messages = [
            # user2先发一条消息，确保存在于metrics中
            {
                "message_id": "msg0",
                "sender": {"id": "user2"},
                "body": {"content": '{"text": "I am here"}'},
            },
            # user1@user2
            {
                "message_id": "msg1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "Hello @user2"}'},
                "mentions": [{"id": {"open_id": "user2"}}],
            },
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        # user2被@了1次
        self.assertEqual(metrics["user2"]["mention_received"], 1)

    def test_topic_initiated(self):
        """测试话题发起计数"""
        messages = [
            {
                "message_id": "topic1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "Topic start"}'},
            },
            {
                "message_id": "reply1",
                "sender": {"id": "user2"},
                "root_id": "topic1",
                "body": {"content": '{"text": "Reply"}'},
            },
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        # user1发起了1个话题
        self.assertEqual(metrics["user1"]["topic_initiated"], 1)

    def test_topic_not_initiated_without_replies(self):
        """测试没有回复的消息不算话题"""
        messages = [
            {
                "message_id": "msg1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "Solo message"}'},
            }
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        # 没有回复，不算话题
        self.assertEqual(metrics["user1"]["topic_initiated"], 0)

    def test_score_calculation(self):
        """测试活跃度分数计算"""
        from config import ACTIVITY_WEIGHTS

        messages = [
            {
                "message_id": "msg1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "Hello"}'},
            }
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        # 1条消息，5个字符
        expected_score = 1 * ACTIVITY_WEIGHTS["message_count"] + 5 * ACTIVITY_WEIGHTS["char_count"]

        self.assertAlmostEqual(metrics["user1"]["score"], expected_score, places=2)

    def test_sender_id_as_string(self):
        """测试sender.id为字符串格式"""
        messages = [
            {
                "message_id": "msg1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "Test"}'},
            }
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        self.assertIn("user1", metrics)

    def test_sender_id_as_dict(self):
        """测试sender.id为字典格式"""
        messages = [
            {
                "message_id": "msg1",
                "sender": {"id": {"open_id": "user1"}},
                "body": {"content": '{"text": "Test"}'},
            }
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        self.assertIn("user1", metrics)

    def test_user_name_mapping(self):
        """测试用户名映射"""
        messages = [
            {
                "message_id": "msg1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "Test"}'},
            }
        ]
        user_names = {"user1": "Alice"}

        calc = MetricsCalculator(messages, user_names)
        metrics = calc.calculate()

        self.assertEqual(metrics["user1"]["user_name"], "Alice")

    def test_user_name_defaults_to_id(self):
        """测试用户名默认使用user_id"""
        messages = [
            {
                "message_id": "msg1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "Test"}'},
            }
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        self.assertEqual(metrics["user1"]["user_name"], "user1")

    def test_multiple_users(self):
        """测试多个用户的指标计算"""
        messages = [
            {
                "message_id": "msg1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "User1 message"}'},
            },
            {
                "message_id": "msg2",
                "sender": {"id": "user2"},
                "body": {"content": '{"text": "User2 message"}'},
            },
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        self.assertEqual(len(metrics), 2)
        self.assertIn("user1", metrics)
        self.assertIn("user2", metrics)

    def test_empty_messages(self):
        """测试空消息列表"""
        calc = MetricsCalculator([])
        metrics = calc.calculate()

        self.assertEqual(metrics, {})

    def test_missing_sender_id(self):
        """测试缺失sender_id的消息"""
        messages = [{"message_id": "msg1", "sender": {}, "body": {"content": '{"text": "Test"}'}}]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        self.assertEqual(metrics, {})


class TestExtractTextFromContent(unittest.TestCase):
    """测试extract_text_from_content静态方法"""

    def test_extract_text_simple(self):
        """测试提取简单文本"""
        content = '{"text": "Hello World"}'

        text, images = MetricsCalculator.extract_text_from_content(content)

        self.assertEqual(text, "Hello World")
        self.assertEqual(images, [])

    def test_extract_text_nested_json(self):
        """测试提取嵌套JSON文本"""
        content = '{"text": "{\\"text\\": \\"Nested\\"}"}'

        text, images = MetricsCalculator.extract_text_from_content(content)

        self.assertEqual(text, "Nested")

    def test_extract_text_from_dict(self):
        """测试从字典提取文本"""
        content = {"text": "Hello"}

        text, images = MetricsCalculator.extract_text_from_content(content)

        self.assertEqual(text, "Hello")

    def test_extract_post_with_title(self):
        """测试提取富文本消息（带标题）"""
        content = {
            "title": "Title",
            "content": [[{"tag": "text", "text": "Line 1"}], [{"tag": "text", "text": "Line 2"}]],
        }

        text, images = MetricsCalculator.extract_text_from_content(content)

        self.assertIn("Title", text)
        self.assertIn("Line 1", text)
        self.assertIn("Line 2", text)

    def test_extract_post_with_images(self):
        """测试提取富文本消息中的图片"""
        content = {
            "content": [[{"tag": "text", "text": "Text"}], [{"tag": "img", "image_key": "img_123"}]]
        }

        text, images = MetricsCalculator.extract_text_from_content(content)

        self.assertIn("Text", text)
        self.assertEqual(images, ["img_123"])

    def test_extract_post_standard_format(self):
        """测试提取标准post格式（带语言版本）"""
        content = {
            "post": {"zh_cn": {"title": "标题", "content": [[{"tag": "text", "text": "内容"}]]}}
        }

        text, images = MetricsCalculator.extract_text_from_content(content)

        self.assertIn("标题", text)
        self.assertIn("内容", text)

    def test_extract_image_key(self):
        """测试提取纯图片消息"""
        content = {"image_key": "img_abc123"}

        text, images = MetricsCalculator.extract_text_from_content(content)

        self.assertIn("image key", text)
        self.assertIn("img_abc123", text)

    def test_extract_file_info(self):
        """测试提取文件消息"""
        content = {"file_name": "document.pdf"}

        text, images = MetricsCalculator.extract_text_from_content(content)

        self.assertIn("file name", text)
        self.assertIn("document.pdf", text)

    def test_extract_empty_content(self):
        """测试空内容"""
        text, images = MetricsCalculator.extract_text_from_content("")

        self.assertEqual(text, "")
        self.assertEqual(images, [])

    def test_extract_none_content(self):
        """测试None内容"""
        text, images = MetricsCalculator.extract_text_from_content(None)

        self.assertEqual(text, "")
        self.assertEqual(images, [])

    def test_extract_malformed_json(self):
        """测试格式错误的JSON"""
        content = '{"text": invalid json'

        text, images = MetricsCalculator.extract_text_from_content(content)

        # 兜底逻辑：返回原始字符串
        self.assertIsInstance(text, str)
        self.assertEqual(images, [])

    def test_extract_at_tag(self):
        """测试提取@标签"""
        content = {"content": [[{"tag": "text", "text": "Hello "}, {"tag": "at", "text": "@user"}]]}

        text, images = MetricsCalculator.extract_text_from_content(content)

        self.assertIn("Hello", text)
        self.assertIn("@user", text)

    def test_extract_link_tag(self):
        """测试提取链接标签"""
        content = {"content": [[{"tag": "a", "text": "Click here"}]]}

        text, images = MetricsCalculator.extract_text_from_content(content)

        self.assertIn("Click here", text)


class TestExtractTextLength(unittest.TestCase):
    """测试_extract_text_length方法"""

    def test_simple_text_length(self):
        """测试简单文本长度"""
        calc = MetricsCalculator([])
        content = '{"text": "Hello"}'

        length = calc._extract_text_length(content)

        self.assertEqual(length, 5)

    def test_text_with_mentions_removed(self):
        """测试@标签被移除后的长度"""
        calc = MetricsCalculator([])
        content = '{"text": "Hello @user World"}'

        length = calc._extract_text_length(content)

        # "@user" 被移除，剩余 "Hello  World"
        self.assertLess(length, 20)

    def test_whitespace_stripped(self):
        """测试空白字符被去除"""
        calc = MetricsCalculator([])
        content = '{"text": "  Hello  "}'

        length = calc._extract_text_length(content)

        self.assertEqual(length, 5)


class TestComplexScenarios(unittest.TestCase):
    """测试复杂场景"""

    def test_full_conversation_metrics(self):
        """测试完整对话的指标计算"""
        messages = [
            # user1发起话题
            {
                "message_id": "topic1",
                "sender": {"id": "user1"},
                "body": {"content": '{"text": "Let\'s discuss this"}'},
            },
            # user2回复并@user3
            {
                "message_id": "reply1",
                "sender": {"id": "user2"},
                "root_id": "topic1",
                "parent_id": "topic1",
                "body": {"content": '{"text": "Good idea @user3"}'},
                "mentions": [{"id": {"open_id": "user3"}}],
            },
            # user3回复
            {
                "message_id": "reply2",
                "sender": {"id": "user3"},
                "root_id": "topic1",
                "parent_id": "reply1",
                "body": {"content": '{"text": "Agreed"}'},
            },
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        # user1: 发起1个话题，收到1条回复
        self.assertEqual(metrics["user1"]["topic_initiated"], 1)
        self.assertEqual(metrics["user1"]["reply_received"], 1)

        # user2: 发了1条消息，收到1条回复
        self.assertEqual(metrics["user2"]["message_count"], 1)
        self.assertEqual(metrics["user2"]["reply_received"], 1)

        # user3: 收到1次@提及，发了1条消息
        self.assertEqual(metrics["user3"]["mention_received"], 1)
        self.assertEqual(metrics["user3"]["message_count"], 1)

    def test_metrics_with_mixed_sender_formats(self):
        """测试混合格式的sender_id"""
        messages = [
            {
                "message_id": "msg1",
                "sender": {"id": "user1"},  # 字符串格式
                "body": {"content": '{"text": "Test"}'},
            },
            {
                "message_id": "msg2",
                "sender": {"id": {"open_id": "user2"}},  # 字典格式
                "body": {"content": '{"text": "Test"}'},
            },
        ]

        calc = MetricsCalculator(messages)
        metrics = calc.calculate()

        self.assertIn("user1", metrics)
        self.assertIn("user2", metrics)


if __name__ == "__main__":
    unittest.main()
