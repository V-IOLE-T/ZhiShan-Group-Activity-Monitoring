import re
import requests
import json
from typing import Optional, Tuple
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
    
    # 支持 docx、doc 和 wiki 链接提取
    DOC_LINK_PATTERN = re.compile(r'https://[\w-]+\.feishu\.cn/(?:docx|doc|wiki)/([\w]+)')

    def __init__(self, auth: FeishuAuth):
        self.auth = auth
        self.mcp_client = MCPClient(auth)

    def extract_token(self, text: str) -> Optional[str]:
        """从文本中提取飞书文档 token"""
        match = self.DOC_LINK_PATTERN.search(text)
        if match:
            token = match.group(1)
            logger.info(f"🔍 识别到文档 Token: {token}")
            return token
        return None

    def process_and_reply(self, message_text: str, chat_id: str) -> bool:
        """
        处理消息并自动回复卡片
        
        Args:
            message_text: 用户发送的消息文本
            chat_id: 聊天会话 ID
            
        Returns:
            是否成功处理并发送
        """
        # 1. 提取 Token
        token = self.extract_token(message_text)
        if not token:
            return False

        # 2. 调用 MCP 获取内容
        logger.info(f"⏳ 正在通过 MCP 获取文档 {token} 的内容...")
        doc_content = self.mcp_client.fetch_doc(token)
        
        if not doc_content:
            self._send_text_reply(chat_id, "❌ 获取文档内容失败，请检查机器人是否拥有该文档的阅读权限。")
            return False

        # 3. 解析文档信息（用于生成图片）
        try:
            content_data = json.loads(doc_content)
            doc_title = content_data.get("title", "文档")
            doc_preview = content_data.get("markdown", content_data.get("message", ""))[:500]
            doc_url = f"https://bytedance.feishu.cn/docx/{token}"
        except Exception as e:
            logger.error(f"❌ 解析文档信息失败: {e}")
            doc_title = "文档"
            doc_preview = "内容获取失败"
            doc_url = f"https://bytedance.feishu.cn/docx/{token}"

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
