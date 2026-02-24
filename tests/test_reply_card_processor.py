"""
reply_card.processor 单元测试

测试 Wiki 文档 token 到 document_id(obj_token) 的解析逻辑。
"""

import unittest
from unittest.mock import patch, call

from reply_card.processor import DocCardProcessor


class FakeAuth:
    """用于测试的最小认证对象"""

    def get_headers(self):
        return {"Authorization": "Bearer test_token", "Content-Type": "application/json"}

    def get_tenant_access_token(self):
        return "test_token"


class TestDocCardProcessor(unittest.TestCase):
    """测试 DocCardProcessor 的 Wiki 解析逻辑"""

    def setUp(self):
        self.processor = DocCardProcessor(FakeAuth())

    def test_extract_doc_reference_for_wiki(self):
        """应正确提取 wiki 链接的类型、token、url"""
        text = "请看这个文档：https://sample.feishu.cn/wiki/wikcnAbCdEf12345?from=from_copylink"
        doc_ref = self.processor.extract_doc_reference(text)

        self.assertIsNotNone(doc_ref)
        doc_type, token, doc_url = doc_ref
        self.assertEqual(doc_type, "wiki")
        self.assertEqual(token, "wikcnAbCdEf12345")
        self.assertIn("/wiki/wikcnAbCdEf12345", doc_url)

    def test_list_wiki_spaces_with_pagination(self):
        """应支持分页拉取知识空间"""
        with patch.object(
            self.processor,
            "_wiki_get",
            side_effect=[
                {"items": [{"space_id": "space_1"}], "has_more": True, "page_token": "next_1"},
                {"items": [{"space_id": "space_2"}], "has_more": False},
            ],
        ) as mock_wiki_get:
            spaces = self.processor._list_wiki_spaces()

        self.assertEqual([space["space_id"] for space in spaces], ["space_1", "space_2"])
        self.assertEqual(
            mock_wiki_get.call_args_list,
            [
                call(self.processor.WIKI_SPACES_URL, {"page_size": 50}),
                call(self.processor.WIKI_SPACES_URL, {"page_size": 50, "page_token": "next_1"}),
            ],
        )

    def test_find_wiki_node_token_in_space_by_obj_token(self):
        """应能在空间节点树中通过 obj_token 找到对应 node_token"""
        with patch.object(
            self.processor,
            "_wiki_get",
            side_effect=[
                {
                    "items": [{"node_token": "node_parent", "obj_token": "obj_parent", "has_child": True}],
                    "has_more": False,
                },
                {
                    "items": [{"node_token": "node_target", "obj_token": "obj_target", "has_child": False}],
                    "has_more": False,
                },
            ],
        ) as mock_wiki_get:
            node_token = self.processor._find_wiki_node_token_in_space("space_1", "obj_target")

        self.assertEqual(node_token, "node_target")
        self.assertEqual(
            mock_wiki_get.call_args_list,
            [
                call(
                    self.processor.WIKI_NODES_URL_TEMPLATE.format(space_id="space_1"),
                    {"page_size": 50},
                ),
                call(
                    self.processor.WIKI_NODES_URL_TEMPLATE.format(space_id="space_1"),
                    {"page_size": 50, "parent_node_token": "node_parent"},
                ),
            ],
        )

    def test_resolve_wiki_document_id_direct_get_node(self):
        """当 get_node 直接命中时，应直接返回 obj_token"""
        with patch.object(
            self.processor, "_fetch_wiki_node_info", return_value={"obj_token": "docx_direct"}
        ) as mock_get_node, patch.object(self.processor, "_list_wiki_spaces") as mock_spaces:
            doc_id = self.processor._resolve_wiki_document_id("wikcnDirect")

        self.assertEqual(doc_id, "docx_direct")
        mock_get_node.assert_called_once_with("wikcnDirect")
        mock_spaces.assert_not_called()

    def test_resolve_wiki_document_id_fallback_spaces_nodes_get_node(self):
        """当直接查询失败时，应走 spaces -> nodes -> get_node 链路"""
        with patch.object(
            self.processor,
            "_fetch_wiki_node_info",
            side_effect=[None, {"obj_token": "docx_from_wiki"}],
        ) as mock_get_node, patch.object(
            self.processor, "_list_wiki_spaces", return_value=[{"space_id": "space_1"}]
        ) as mock_spaces, patch.object(
            self.processor, "_find_wiki_node_token_in_space", return_value="wikcnNodeResolved"
        ) as mock_find_node:
            doc_id = self.processor._resolve_wiki_document_id("wikcnFromUrl")

        self.assertEqual(doc_id, "docx_from_wiki")
        self.assertEqual(
            mock_get_node.call_args_list,
            [call("wikcnFromUrl"), call("wikcnNodeResolved")],
        )
        mock_spaces.assert_called_once()
        mock_find_node.assert_called_once_with("space_1", "wikcnFromUrl")


if __name__ == "__main__":
    unittest.main()
