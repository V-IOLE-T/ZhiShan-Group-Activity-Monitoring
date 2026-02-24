import re
import requests
import json
import html
from typing import Optional, Tuple, Dict, Any, List, Set
from urllib.parse import urlparse
from .mcp_client import MCPClient
from .card_builder import CardBuilder
from auth import FeishuAuth
from logger import get_logger

logger = get_logger(__name__)

class DocCardProcessor:
    """
    文档卡片处理流程类
    整合 提取链接 -> MCP获取 -> 生成卡片 -> 发送消息
    """
    
    DOC_TYPE_SET = {"docx", "doc", "wiki", "docs"}
    DOC_URL_PATTERN = re.compile(r'https?://[^\s"\'<>]+', re.IGNORECASE)
    WIKI_SPACES_URL = "https://open.feishu.cn/open-apis/wiki/v2/spaces"
    WIKI_NODES_URL_TEMPLATE = "https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"
    WIKI_GET_NODE_URL = "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node"

    def __init__(self, auth: FeishuAuth):
        self.auth = auth
        self.mcp_client = MCPClient(auth)

    def _parse_doc_url(self, doc_url: str) -> Optional[Tuple[str, str]]:
        """解析飞书文档 URL，返回 (doc_type, token)"""
        try:
            parsed = urlparse(doc_url)
            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) < 2:
                return None
            doc_type = path_parts[0].lower()
            if doc_type not in self.DOC_TYPE_SET:
                return None
            token = path_parts[1].strip()
            if not token:
                return None
            return doc_type, token
        except Exception:
            return None

    def extract_token(self, text: str) -> Optional[str]:
        """从文本中提取飞书文档 token（支持 feishu/larksuite）"""
        doc_url = self.extract_doc_url(text)
        if not doc_url:
            return None
        parsed_doc = self._parse_doc_url(doc_url)
        if parsed_doc:
            _, token = parsed_doc
            logger.info(f"🔍 识别到文档 Token: {token}")
            return token
        return None

    def extract_doc_url(self, text: str) -> Optional[str]:
        """从文本中提取飞书文档 URL"""
        source_text = (text or "").replace("\\/", "/")
        for candidate in self.DOC_URL_PATTERN.findall(source_text):
            url = candidate.rstrip("。,.，；;）)]》>\"'!?！？}\\")
            try:
                parsed = urlparse(url)
                host = (parsed.hostname or "").lower()
                path_parts = [p for p in parsed.path.split("/") if p]
                if not (host.endswith("feishu.cn") or host.endswith("larksuite.cn")):
                    continue
                if len(path_parts) < 2:
                    continue
                if path_parts[0].lower() in self.DOC_TYPE_SET:
                    return url
            except Exception:
                continue
        return None

    def extract_doc_reference(self, text: str) -> Optional[Tuple[str, str, str]]:
        """提取文档引用，返回 (doc_type, token, url)"""
        doc_url = self.extract_doc_url(text)
        if not doc_url:
            return None
        parsed_doc = self._parse_doc_url(doc_url)
        if not parsed_doc:
            return None
        doc_type, token = parsed_doc
        return doc_type, token, doc_url

    def _wiki_get(self, url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """调用 Wiki GET API，失败返回 None"""
        try:
            response = requests.get(url, headers=self.auth.get_headers(), params=params, timeout=10)
            data = response.json()
        except Exception as e:
            logger.error(f"❌ Wiki API 调用异常: {url}, error={e}")
            return None

        if response.status_code != 200:
            logger.error(f"❌ Wiki API HTTP失败: {url}, status={response.status_code}, body={data}")
            return None

        if data.get("code") != 0:
            logger.warning(
                f"⚠️ Wiki API 业务失败: {url}, code={data.get('code')}, msg={data.get('msg')}"
            )
            return None

        return data.get("data") or {}

    def _list_wiki_spaces(self) -> List[Dict[str, Any]]:
        """分页获取有权限访问的知识空间列表"""
        items: List[Dict[str, Any]] = []
        page_token: Optional[str] = None

        while True:
            params: Dict[str, Any] = {"page_size": 50}
            if page_token:
                params["page_token"] = page_token

            data = self._wiki_get(self.WIKI_SPACES_URL, params)
            if data is None:
                break

            items.extend(data.get("items") or [])
            if not data.get("has_more"):
                break

            page_token = data.get("page_token")
            if not page_token:
                break

        return items

    def _fetch_wiki_node_info(self, token: str) -> Optional[Dict[str, Any]]:
        """获取 Wiki 节点信息"""
        data = self._wiki_get(self.WIKI_GET_NODE_URL, {"token": token, "obj_type": "wiki"})
        if not data:
            return None
        node = data.get("node")
        return node if isinstance(node, dict) else None

    def _find_wiki_node_token_in_space(self, space_id: str, target_token: str) -> Optional[str]:
        """
        在知识空间内分页扫描节点，找到目标 token 对应的 node_token
        target_token 可匹配 node_token 或 obj_token
        """
        if not space_id:
            return None

        pending_parents: List[Optional[str]] = [None]
        visited_parents: Set[str] = set()

        while pending_parents:
            parent_node_token = pending_parents.pop(0)
            page_token: Optional[str] = None

            while True:
                params: Dict[str, Any] = {"page_size": 50}
                if parent_node_token:
                    params["parent_node_token"] = parent_node_token
                if page_token:
                    params["page_token"] = page_token

                nodes_url = self.WIKI_NODES_URL_TEMPLATE.format(space_id=space_id)
                data = self._wiki_get(nodes_url, params)
                if data is None:
                    break

                for item in data.get("items") or []:
                    node_token = item.get("node_token")
                    obj_token = item.get("obj_token")

                    if target_token in (node_token, obj_token):
                        return node_token

                    if item.get("has_child") and node_token and node_token not in visited_parents:
                        visited_parents.add(node_token)
                        pending_parents.append(node_token)

                if not data.get("has_more"):
                    break

                page_token = data.get("page_token")
                if not page_token:
                    break

        return None

    def _resolve_wiki_document_id(self, wiki_token: str) -> Optional[str]:
        """
        将 Wiki URL token 解析为可用于 fetch-doc 的 document_id(obj_token)
        1) 先尝试直接 get_node
        2) 失败则按 spaces -> nodes -> get_node 三步解析
        """
        node = self._fetch_wiki_node_info(wiki_token)
        if node and node.get("obj_token"):
            return node.get("obj_token")

        logger.info("ℹ️ 直接 get_node 未命中，尝试 spaces -> nodes -> get_node 链路解析 Wiki 文档")
        spaces = self._list_wiki_spaces()
        for space in spaces:
            space_id = space.get("space_id")
            if not space_id:
                continue
            node_token = self._find_wiki_node_token_in_space(space_id, wiki_token)
            if not node_token:
                continue

            node_info = self._fetch_wiki_node_info(node_token)
            if node_info and node_info.get("obj_token"):
                return node_info.get("obj_token")

        return None

    def _sanitize_preview_text(self, text: str) -> str:
        """清洗飞书 markdown 中的富文本标签，避免渲染出 <text>/<mention-doc>"""
        cleaned = html.unescape(str(text or "")).replace("\\n", "\n")
        cleaned = re.sub(r"<mention-doc[^>]*>(.*?)</mention-doc>", r"\1", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"</?text[^>]*>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"</?mention-user[^>]*>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def process_and_reply(self, message_text: str, chat_id: str) -> bool:
        """
        处理消息并自动回复卡片
        
        Args:
            message_text: 用户发送的消息文本
            chat_id: 聊天会话 ID
            
        Returns:
            是否成功处理并发送
        """
        # 1. 提取 Token / URL
        doc_ref = self.extract_doc_reference(message_text)
        if not doc_ref:
            return False
        doc_type, token, doc_url = doc_ref
        doc_id = token

        # Wiki 链接需要先换取实际文档 obj_token(document_id)
        if doc_type == "wiki":
            logger.info(f"⏳ 检测到 Wiki 链接，开始解析真实 document_id: token={token}")
            resolved_doc_id = self._resolve_wiki_document_id(token)
            if not resolved_doc_id:
                logger.error("❌ Wiki document_id 解析失败")
                self._send_text_reply(
                    chat_id,
                    "❌ 无法解析知识库文档 ID，请确认机器人已加入知识空间并具备节点阅读权限。",
                )
                return False
            doc_id = resolved_doc_id
            logger.info(f"✅ Wiki document_id 解析成功: {doc_id}")

        # 2. 调用 MCP 获取内容
        logger.info(f"⏳ 正在通过 MCP 获取文档内容，doc_id={doc_id} ...")
        doc_content = self.mcp_client.fetch_doc(doc_id)

        # token 失败时，再尝试 URL 兜底
        if not doc_content and doc_url:
            logger.info("🔄 token 模式未取到内容，尝试 URL 模式...")
            doc_content = self.mcp_client.fetch_doc(doc_url)
        
        # [调试日志] 显示 MCP 返回结果
        if doc_content:
            logger.info(f"✅ MCP 成功返回内容，长度: {len(doc_content)} 字符")
            logger.info(f"📄 内容预览: {doc_content[:200]}...")
        else:
            logger.error(f"❌ MCP 返回空内容或调用失败")
        
        if not doc_content:
            self._send_text_reply(chat_id, "❌ 获取文档内容失败，请检查机器人是否拥有该文档的阅读权限。")
            return False

        # 3. 解析文档信息（用于生成图片）
        try:
            content_data = json.loads(doc_content)
            if isinstance(content_data, dict):
                doc_title = content_data.get("title") or content_data.get("doc_title") or "文档"
                raw_preview = (
                    content_data.get("markdown")
                    or content_data.get("content")
                    or content_data.get("message")
                    or content_data.get("text")
                    or ""
                )
                if isinstance(raw_preview, (dict, list)):
                    raw_preview = json.dumps(raw_preview, ensure_ascii=False)
                doc_preview = str(raw_preview)
            else:
                doc_title = "文档"
                doc_preview = str(content_data)
            
            # [调试日志] 显示解析结果
            logger.info(f"📋 解析成功 - 标题: {doc_title}")
            logger.info(f"📋 预览内容长度: {len(doc_preview)} 字符")
            logger.info(f"📋 预览内容: {doc_preview[:100]}...")
        except json.JSONDecodeError:
            doc_title = "文档"
            doc_preview = doc_content
            logger.info("ℹ️ MCP 返回纯文本内容，按文本预览处理")
        except Exception as e:
            logger.error(f"❌ 解析文档信息失败: {e}")
            logger.error(f"原始内容: {doc_content[:200] if doc_content else 'None'}...")
            doc_title = "文档"
            doc_preview = "内容获取失败"

        doc_preview = self._sanitize_preview_text(doc_preview)[:500]
        if not doc_preview.strip():
            doc_preview = "文档内容已获取，请点击原文查看完整内容。"

        # 4. 构建并发送卡片 (已按需求移除)
        # card_content = CardBuilder.build_doc_card(doc_content, token)
        # card_success = self._send_card_reply(chat_id, card_content)
        
        # 5. 生成并发送卡片样式图片
        try:
            from .card_style_generator import CardStyleImageGenerator
            generator = CardStyleImageGenerator()
            image_data = generator.generate_card_image(doc_title, doc_preview)
            self._send_image_reply(chat_id, image_data)
            logger.info("✅ 卡片样式图片发送成功")
        except Exception as e:
            logger.error(f"⚠️ 图片生成或发送失败: {e}")
            import traceback
            traceback.print_exc()
            # 图片发送失败不影响整体流程
        
        return True

    def _send_text_reply(self, chat_id: str, text: str):
        """发送纯文本回复"""
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
        headers = self.auth.get_headers()
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": f'{{"text":"{text}"}}'
        }
        requests.post(url, headers=headers, json=payload)

    def _send_card_reply(self, chat_id: str, card_content: dict) -> bool:
        """发送卡片回复"""
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
        headers = self.auth.get_headers()
        payload = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card_content)
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            res_data = response.json()
            if res_data.get("code") == 0:
                logger.info(f"✅ 卡片消息发送成功")
                return True
            else:
                logger.error(f"❌ 卡片消息发送失败: {res_data.get('msg')}")
                return False
        except Exception as e:
            logger.error(f"❌ 发送卡片异常: {str(e)}")
            return False

    def _send_image_reply(self, chat_id: str, image_data: bytes) -> bool:
        """发送图片回复"""
        # 第一步：上传图片获取 image_key
        upload_url = "https://open.feishu.cn/open-apis/im/v1/images"
        
        # 上传文件时，只需要 Authorization，不要 Content-Type
        token = self.auth.get_tenant_access_token()
        upload_headers = {
            "Authorization": f"Bearer {token}"
        }
        
        files = {
            'image': ('doc_summary.png', image_data, 'image/png')
        }
        data = {
            'image_type': 'message'
        }
        
        try:
            # 上传图片
            upload_response = requests.post(upload_url, headers=upload_headers, files=files, data=data, timeout=10)
            upload_data = upload_response.json()
            
            if upload_data.get("code") != 0:
                logger.error(f"❌ 图片上传失败: {upload_data.get('msg')}")
                return False
            
            image_key = upload_data.get("data", {}).get("image_key")
            if not image_key:
                logger.error("❌ 未获取到 image_key")
                return False
            
            # 第二步：发送图片消息
            send_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
            send_headers = self.auth.get_headers()
            payload = {
                "receive_id": chat_id,
                "msg_type": "image",
                "content": json.dumps({"image_key": image_key})
            }
            
            send_response = requests.post(send_url, headers=send_headers, json=payload, timeout=10)
            send_data = send_response.json()
            
            if send_data.get("code") == 0:
                return True
            else:
                logger.error(f"❌ 图片消息发送失败: {send_data.get('msg')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 发送图片异常: {str(e)}")
            return False
