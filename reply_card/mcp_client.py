import requests
import json
from typing import Dict, Any, Optional
from auth import FeishuAuth
from logger import get_logger

logger = get_logger(__name__)

class MCPClient:
    """
    飞书 MCP 服务客户端
    用于调用飞书官方部署的远程 MCP 工具
    """
    
    BASE_URL = "https://mcp.feishu.cn/mcp"
    
    def __init__(self, auth: FeishuAuth):
        self.auth = auth

    def call_tool(self, tool_name: str, arguments: Dict[str, Any], max_retries: int = 1) -> Optional[Dict[str, Any]]:
        """
        调用指定的 MCP 工具（带重试机制）

        Args:
            tool_name: 工具名称，如 'fetch-doc'
            arguments: 工具入参
            max_retries: 最大重试次数（默认1次，即共2次尝试）

        Returns:
            工具返回的结果，失败返回 None
        """
        token = self.auth.get_tenant_access_token()

        headers = {
            "Content-Type": "application/json",
            "X-Lark-MCP-TAT": token,
            "X-Lark-MCP-Allowed-Tools": tool_name
        }

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        for attempt in range(max_retries + 1):
            try:
                logger.info(f"🚀 调用 MCP 工具: {tool_name}, 参数: {arguments}")
                if attempt > 0:
                    logger.info(f"🔄 第 {attempt + 1} 次尝试...")

                # 缩短超时从20秒到10秒
                response = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=10)

                logger.info(f"📡 HTTP状态码: {response.status_code}")

                result = response.json()

                if "error" in result:
                    error_msg = result['error']
                    logger.error(f"❌ MCP 调用失败: {error_msg}")

                    # 可重试的错误类型
                    if attempt < max_retries and self._is_retryable_error(error_msg):
                        import time
                        wait_time = 2 ** attempt  # 指数退避
                        logger.info(f"⏳ {wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue

                    return None

                if result.get("result", {}).get("isError"):
                    logger.error(f"❌ MCP 工具内部错误: {result['result'].get('content')}")
                    # 工具内部错误不重试
                    return None

                logger.info(f"✅ MCP 调用成功")
                return result.get("result")

            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ MCP 请求超时（10秒）")
                if attempt < max_retries:
                    import time
                    wait_time = 2 ** attempt
                    logger.info(f"⏳ {wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"❌ MCP 请求超时，已重试 {max_retries} 次")
                return None

            except requests.exceptions.ConnectionError as e:
                logger.error(f"❌ MCP 连接失败: {str(e)}")
                logger.error(f"   可能原因: 云服务器无法访问 {self.BASE_URL}")
                # 连接错误不重试
                return None

            except Exception as e:
                logger.error(f"❌ MCP 请求异常: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                # 其他异常不重试
                return None

        return None

    def _is_retryable_error(self, error: Any) -> bool:
        """
        判断错误是否可重试

        Args:
            error: 错误信息

        Returns:
            是否可重试
        """
        if not isinstance(error, dict):
            return False

        code = error.get("code", -1)
        message = error.get("message", "")

        # 可重试的错误码
        RETRYABLE_CODES = [
            -1,  # 未知错误
            9999,  # 系统繁忙
        ]

        # 可重试的错误消息关键词
        RETRYABLE_KEYWORDS = [
            "timeout",
            "超时",
            "系统繁忙",
            "rate limit",
            "限流"
        ]

        if code in RETRYABLE_CODES:
            return True

        message_lower = str(message).lower()
        for keyword in RETRYABLE_KEYWORDS:
            if keyword in message_lower:
                return True

        return False

    def fetch_doc(self, doc_id: str) -> Optional[str]:
        """
        获取云文档内容
        
        Args:
            doc_id: 文档的 token (docx_token)
            
        Returns:
            文档内容字符串（通常是 JSON 格式的字符串）
        """
        result = self.call_tool("fetch-doc", {"docID": doc_id})
        if result and "content" in result:
            # MCP 的 content 常常是一个列表，其中包含 type='text' 的项
            for item in result["content"]:
                if item.get("type") == "text":
                    return item.get("text")
        return None
