import re
import requests
import json
import threading
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from .mcp_client import MCPClient
from .card_builder import CardBuilder
from .placeholder_generator import generate_placeholder, generate_with_theme
from auth import FeishuAuth
from logger import get_logger

logger = get_logger(__name__)

# 线程池限制：最多5个并发图片生成
_MAX_ASYNC_THREADS = 5
_thread_pool = ThreadPoolExecutor(max_workers=_MAX_ASYNC_THREADS, thread_name_prefix="async_card")


class DocCardProcessor:
    """
    文档卡片处理流程类 - 两阶段处理版本

    整合 提取链接 -> 同步回复(占位图) -> 异步生成(完整图片)

    两阶段处理：
    1. 同步阶段（<5秒）：提取文档信息，发送文字 + 占位图
    2. 异步阶段：后台线程生成完整图片并推送
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
        处理消息并自动回复卡片（两阶段模式）

        阶段1（同步）：发送文字 + 占位图
        阶段2（异步）：后台生成完整图片并推送

        Args:
            message_text: 用户发送的消息文本
            chat_id: 聊天会话 ID

        Returns:
            是否成功处理
        """
        # 1. 提取 Token
        token = self.extract_token(message_text)
        if not token:
            return False

        # 2. 快速响应：发送文字 + 占位图
        sync_success = self.sync_reply(token, chat_id)

        if not sync_success:
            return False

        # 3. 异步生成：后台线程生成完整图片
        self._async_generate_and_push(token, chat_id)

        return True

    def sync_reply(self, token: str, chat_id: str) -> bool:
        """
        同步响应阶段（<5秒）

        发送：
        1. 文字提示："正在为您生成文档摘要..."
        2. 占位图："正在生成卡片，请稍候..."

        Args:
            token: 文档 Token
            chat_id: 聊天会话 ID

        Returns:
            是否成功发送
        """
        # 发送文字提示
        self._send_text_reply(chat_id, "⏳ 正在为您生成文档摘要，请稍候...")

        # 发送占位图
        try:
            placeholder_data = generate_with_theme(
                title="文档处理中",
                message=f"正在解析文档内容...\n文档 Token: {token[:16]}..."
            )
            self._send_image_reply(chat_id, placeholder_data)
            logger.info("✅ 同步响应发送成功（占位图）")
            return True
        except Exception as e:
            logger.error(f"⚠️ 占位图发送失败: {e}")
            # 即使占位图失败，文字已发送，继续异步处理
            return True

    def _async_generate_and_push(self, token: str, chat_id: str):
        """
        异步生成并推送完整图片

        在后台线程中：
        1. 调用 MCP 获取文档内容
        2. 生成完整卡片图片
        3. 推送图片消息

        Args:
            token: 文档 Token
            chat_id: 聊天会话 ID
        """
        def async_task():
            try:
                # 1. 调用 MCP 获取内容
                logger.info(f"⏳ [异步] 正在通过 MCP 获取文档 {token} 的内容...")
                doc_content = self.mcp_client.fetch_doc(token)

                if not doc_content:
                    logger.error(f"❌ [异步] MCP 返回空内容")
                    self._send_text_reply(chat_id, "⚠️ 文档内容获取失败，请稍后重试。")
                    return

                # 2. 解析文档信息
                try:
                    content_data = json.loads(doc_content)
                    doc_title = content_data.get("title", "文档")
                    doc_preview = content_data.get("markdown", content_data.get("message", ""))[:500]
                except Exception as e:
                    logger.error(f"❌ [异步] 解析文档信息失败: {e}")
                    doc_title = "文档"
                    doc_preview = "内容解析失败"

                # 3. 生成完整图片
                from .card_style_generator import CardStyleImageGenerator
                generator = CardStyleImageGenerator()
                image_data = generator.generate_card_image(doc_title, doc_preview)

                # 4. 推送完整图片
                success = self._send_image_reply(chat_id, image_data)
                if success:
                    logger.info("✅ [异步] 完整图片推送成功")
                else:
                    logger.error("❌ [异步] 完整图片推送失败")
                    # 降级：发送文字说明
                    self._send_text_reply(chat_id, f"📄 {doc_title}\n{doc_preview[:200]}...")

            except Exception as e:
                logger.error(f"❌ [异步] 处理异常: {e}")
                import traceback
                logger.error(traceback.format_exc())

        # 提交到线程池
        _thread_pool.submit(async_task)

    def process_and_reply_legacy(self, message_text: str, chat_id: str) -> bool:
        """
        处理消息并自动回复卡片（原始同步版本，用于降级）

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

        if doc_content:
            logger.info(f"✅ MCP 成功返回内容，长度: {len(doc_content)} 字符")
        else:
            logger.error(f"❌ MCP 返回空内容或调用失败")

        if not doc_content:
            self._send_text_reply(chat_id, "❌ 获取文档内容失败，请检查机器人是否拥有该文档的阅读权限。")
            return False

        # 3. 解析文档信息
        try:
            content_data = json.loads(doc_content)
            doc_title = content_data.get("title", "文档")
            doc_preview = content_data.get("markdown", content_data.get("message", ""))[:500]
        except Exception as e:
            logger.error(f"❌ 解析文档信息失败: {e}")
            doc_title = "文档"
            doc_preview = "内容获取失败"

        # 4. 生成并发送卡片样式图片
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
        try:
            requests.post(url, headers=headers, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"❌ 发送文字异常: {e}")

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


def shutdown_thread_pool():
    """关闭线程池（用于程序退出时清理）"""
    global _thread_pool
    if _thread_pool:
        _thread_pool.shutdown(wait=False)
        logger.info("✅ 异步卡片线程池已关闭")
