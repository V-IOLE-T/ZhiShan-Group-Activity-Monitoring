import json
from typing import Dict, Any

class CardBuilder:
    """
    飞书消息卡片构建器
    支持两种模式：
    1. 模板模式：使用搭建工具创建的卡片模板
    2. JSON 模式：直接构建卡片 JSON
    """

    # 配置：卡片模板信息（请在搭建工具中创建后填写）
    TEMPLATE_ID = "AAqv4EFhJ1zyV"  # 例如：AAqyjwfhabcef
    TEMPLATE_VERSION = "1.0.1"  # 卡片版本号
    USE_TEMPLATE = True  # 是否使用模板模式

    @staticmethod
    def build_doc_card(doc_content_str: str, doc_token: str) -> Dict[str, Any]:
        """
        构建文档信息卡片
        
        Args:
            doc_content_str: MCP 返回的文档内容字符串
            doc_token: 文档标识符，用于生成跳转链接
            
        Returns:
            飞书卡片 JSON 结构或模板结构
        """
        preview_text = "无法解析文档内容"
        
        try:
            # MCP 返回的文本通常是一个包含 'data' 字段的 JSON 字符串
            content_data = json.loads(doc_content_str)
            
            # 打印调试信息（帮助理解数据结构）
            print(f"  > [调试] MCP 返回数据的顶层键: {list(content_data.keys())}")
            
            # MCP 实际返回的结构包含：markdown, message, title 等字段
            # 提取标题
            doc_title = content_data.get("title", "文档")
            
            # 优先使用 markdown（文档正文），message 只是状态消息
            text_content = content_data.get("markdown", "")
            
            if not text_content:
                # 如果 markdown 为空，尝试使用 message（但这通常只是状态信息）
                text_content = content_data.get("message", "")
            
            print(f"  > [调试] 文档标题: {doc_title}")
            print(f"  > [调试] 提取的文本长度: {len(text_content)} 字符")
            
            if text_content and len(text_content.strip()) > 0:
                # 截取前 300 字
                preview_text = text_content.strip()[:300]
                if len(text_content) > 300:
                    preview_text += "..."
                
                print(f"  > [调试] 文本预览: {preview_text[:100]}...")
            else:
                print(f"  > [警告] 未能提取到有效文本内容")
                preview_text = "文档内容已成功获取，点击下方按钮查看详情。"

        except Exception as e:
            print(f"  > [错误] 文本提取异常: {e}")
            import traceback
            traceback.print_exc()
            preview_text = "文档内容解析说明：该文档包含丰富格式，请点击链接查看详情。"
            doc_title = "文档"

        # 构建文档链接
        doc_url = f"https://bytedance.feishu.cn/docx/{doc_token}"
        
        # 判断使用模板模式还是 JSON 模式
        if CardBuilder.USE_TEMPLATE and CardBuilder.TEMPLATE_ID:
            # 模板模式：使用搭建工具创建的卡片
            return {
                "type": "template",
                "data": {
                    "template_id": CardBuilder.TEMPLATE_ID,
                    "template_version_name": CardBuilder.TEMPLATE_VERSION,
                    "template_variable": {
                        "doc_title": doc_title,      # 文档标题变量
                        "doc_preview": preview_text,  # 文档预览内容变量
                        "doc_url": doc_url            # 文档链接变量
                    }
                }
            }
        else:
            # JSON 模式：直接构建卡片结构
            return CardBuilder._build_json_card(preview_text, doc_url, doc_title)

    @staticmethod
    def _build_json_card(preview_text: str, doc_url: str, doc_title: str = "文档") -> Dict[str, Any]:
        """构建 JSON 格式的卡片（备用方案）"""
        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "template": "blue",
                "title": {
                    "content": f"📑 {doc_title}",
                    "tag": "plain_text"
                }
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": f"**文档预览：**\n{preview_text}",
                        "tag": "lark_md"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "content": "查看文档详情",
                                "tag": "plain_text"
                            },
                            "url": doc_url,
                            "type": "primary"
                        }
                    ]
                }
            ]
        }
        
        return card

