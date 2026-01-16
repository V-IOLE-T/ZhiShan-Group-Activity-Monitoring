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

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        调用指定的 MCP 工具
        
        Args:
            tool_name: 工具名称，如 'fetch-doc'
            arguments: 工具入参
            
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
        
        try:
            logger.info(f"🚀 调用 MCP 工具: {tool_name}, 参数: {arguments}")
            logger.info(f"🌐 请求URL: {self.BASE_URL}")
            logger.info(f"🔑 使用Token前缀: {token[:20]}...")
            
            response = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=20)
            
            logger.info(f"📡 HTTP状态码: {response.status_code}")
            logger.info(f"📡 响应内容: {response.text[:500]}...")
            
            result = response.json()
            
            if "error" in result:
                logger.error(f"❌ MCP 调用失败: {result['error']}")
                return None
                
            if result.get("result", {}).get("isError"):
                logger.error(f"❌ MCP 工具内部错误: {result['result'].get('content')}")
                return None
                
            logger.info(f"✅ MCP 调用成功")
            return result.get("result")
        except requests.exceptions.Timeout:
            logger.error(f"❌ MCP 请求超时（20秒）")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ MCP 连接失败: {str(e)}")
            logger.error(f"   可能原因: 云服务器无法访问 {self.BASE_URL}")
            return None
        except Exception as e:
            logger.error(f"❌ MCP 请求异常: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None

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
