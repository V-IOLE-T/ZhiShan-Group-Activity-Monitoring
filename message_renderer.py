"""
消息转文档渲染模块

负责将飞书IM消息的富文本内容(Post/Rich Text)转换为飞书云文档(Docx)的Block结构
支持文本样式(加粗/斜体/下划线/删除线)、链接、图片、@提及等元素的转换
"""

import json
from typing import List, Dict, Any, Tuple

class MessageToDocxConverter:
    """
    消息内容转换器
    """
    
    def __init__(self, storage_client):
        """
        Args:
            storage_client: DocxStorage实例，用于图片转存
        """
        self.storage = storage_client

    def convert(self, message_content_json: str, message_id: str, doc_id: str, 
                sender_name: str = "", send_time: str = "", 
                is_reply: bool = False, parent_sender_name: str = None,
                remove_tag: str = None) -> List[Dict[str, Any]]:
        """
        将消息内容转换为Docx Block列表
        
        Args:
            message_content_json: 消息内容的JSON字符串
            message_id: 原始消息ID(用于下载资源)
            doc_id: 目标文档ID(用于上传资源挂载)
            sender_name: 发送者昵称
            send_time: 发送时间
            is_reply: 是否是回复消息
            parent_sender_name: 被回复者的昵称（用于嵌套回复）
            remove_tag: 需要移除的标签（不含#）
            
        Returns:
            Docx Block 结构列表
        """
        blocks = []
        
        # 0. 根据是否是回复，使用不同的信息头格式
        if is_reply:
            # 回复格式：先加空行
            blocks.append(self._create_text_block(""))  # 空行
            
            # 构建回复头文本
            header_text = "💬 "
            if sender_name:
                header_text += f"{sender_name}"
            
            # 如果有被回复者，显示 "A ↩️ B"
            if parent_sender_name:
                header_text += f" ↩️ {parent_sender_name}"
            else:
                # 默认回复楼主
                header_text += " ↩️ 楼主"
                
            if send_time:
                header_text += f"  ⏰ {send_time}"
                
            blocks.append(self._create_text_block_from_elements([
                self._create_text_run(header_text, {"italic": True})
            ]))
        elif sender_name or send_time:
            # 原始消息格式
            header_text = ""
            if sender_name:
                header_text += f"📤 {sender_name}"
            if send_time:
                header_text += f"  ⏰ {send_time}"
            blocks.append(self._create_text_block_from_elements([
                self._create_text_run(header_text, {"bold": True})
            ]))
        
        try:
            content_obj = json.loads(message_content_json)
        except json.JSONDecodeError:
            # 如果不是JSON，当作纯文本处理（检查是否是代码块）
            if message_content_json.strip().startswith('```'):
                # 处理代码块
                code_content = message_content_json.strip()
                if code_content.startswith('```') and code_content.endswith('```'):
                    code_content = code_content[3:-3].strip()
                    # 检测语言
                    lines = code_content.split('\n')
                    if lines:
                        first_line = lines[0].strip().lower()
                        code_content = '\n'.join(lines[1:]) if len(lines) > 1 else ''
                    blocks.append(self._create_code_block(code_content))
                else:
                    blocks.append(self._create_text_block(message_content_json))
            else:
                blocks.append(self._create_text_block(message_content_json))
            
            # 只有非回复消息才加分割线
            if not is_reply:
                blocks.append(self._create_divider_block())
            return blocks

        if isinstance(content_obj, dict) and isinstance(content_obj.get("post"), dict):
            post_content = content_obj["post"]
            if isinstance(post_content.get("zh_cn"), dict):
                content_obj = post_content["zh_cn"]
            else:
                first_locale_content = next(
                    (value for value in post_content.values() if isinstance(value, dict)),
                    None,
                )
                if first_locale_content is not None:
                    content_obj = first_locale_content
            
        # 1. 提取标题 (如果有)
        title = content_obj.get("title", "")
        if title:
            blocks.append(self._create_heading_block(title, 1))
            
        # 2. 遍历内容 (Post结构通常是 content -> [[elements], [elements]])
        # 这里的 content 是一个二维数组，外层是段落，内层是段落内的元素
        # 或者有时是打平的结构，视消息类型而定
        
        # 检查是否是富文本 post 结构
        body_content = content_obj.get("content", [])
        
        # 如果 content 为空或者不是列表，检查是否是纯文本消息 (key="text") 或 纯图片消息 (key="image_key")
        if not body_content or not isinstance(body_content, list):
            # 1. 检查纯图片消息
            image_key = content_obj.get("image_key")
            if image_key:
                file_token = self.storage.transfer_image_to_docx(message_id, image_key, doc_id)
                if file_token:
                    blocks.append(self._create_image_block(file_token))
            
            # 2. 检查纯文本消息
            else:
                text_content = content_obj.get("text", "")
                if text_content:
                    # 纯文本消息
                    if remove_tag:
                        text_content = text_content.replace(f"#{remove_tag}", "")
                    blocks.append(self._create_text_block(text_content))
                else:
                    # 既没有 content 也没有 text，尝试转字符串
                    if body_content:
                        text_content = str(body_content)
                        if remove_tag:
                            text_content = text_content.replace(f"#{remove_tag}", "")
                        blocks.append(self._create_text_block(text_content))

        # 遍历段落
        for paragraph in body_content:
            if not isinstance(paragraph, list):
                continue
                
            # 每个 paragraph 转换为一个 block (通常是 TextBlock，除非包含独立图片)
            # 在 Message 中，图片通常作为独立元素或是行内元素
            # 在 Docx 中，图片必须是独立的 ImageBlock (或浮动，可以先简化为独立块)
            
            # 我们采取的策略：
            # 遍历行内元素，收集 TextRun；
            # 遇到 Image，先结束当前的 TextBlock，插入 ImageBlock，再开启新的 TextBlock (如果后面还有字)
            
            current_text_elements = []
            
            for element in paragraph:
                tag = element.get("tag", "text")
                
                if tag == "text":
                    style = self._parse_style(element.get("style", []), element.get("un_style", []))
                    content_text = element.get("text", "")
                    if remove_tag:
                        content_text = content_text.replace(f"#{remove_tag}", "")
                    current_text_elements.append(
                        self._create_text_run(content_text, style)
                    )
                    
                elif tag == "a":
                    # 链接
                    style = self._parse_style(element.get("style", []), [])
                    # Docx Link 也是 TextRun，只是多了 text_element_style.link
                    text_run = self._create_text_run(element.get("text", ""), style)
                    if "text_element_style" not in text_run["text_run"]:
                        text_run["text_run"]["text_element_style"] = {}
                    text_run["text_run"]["text_element_style"]["link"] = {"url": element.get("href", "")}
                    current_text_elements.append(text_run)
                    
                elif tag == "at":
                    # @提及 -> 简化为加粗文本
                    user_name = element.get("user_name", "unknown")
                    current_text_elements.append(
                        self._create_text_run(f"@{user_name} ", {"bold": True})
                    )
                
                elif tag == "img":
                    # 图片：需要先上传，然后在 storage.py 中用三步流程处理
                    # 1. 如果有积攒的文本，先生成 TextBlock
                    if current_text_elements:
                        blocks.append(self._create_text_block_from_elements(current_text_elements))
                        current_text_elements = []
                    
                    # 2. 处理图片（不再添加占位文本）
                    img_key = element.get("image_key")
                    if img_key:
                        file_token = self.storage.transfer_image_to_docx(message_id, img_key, doc_id)
                        if file_token:
                            blocks.append(self._create_image_block(file_token))
                        # 图片失败时静默跳过，不添加失败提示
                
                elif tag == "md":
                    # Markdown 暂不支持完全解析，转为文本
                    content_text = element.get("text", "")
                    if remove_tag:
                        content_text = content_text.replace(f"#{remove_tag}", "")
                    current_text_elements.append(
                        self._create_text_run(content_text)
                    )

            # 段落结束，如果还有文本，生成 Block
            if current_text_elements:
                # 检查第一个元素的文本，判断是否是列表项
                first_text = ""
                if current_text_elements:
                    first_run = current_text_elements[0].get("text_run", {})
                    first_text = first_run.get("content", "")
                
                # 有序列表检测（1. 2. 等）
                if first_text and len(first_text) >= 2 and first_text[0].isdigit() and first_text[1:3].startswith('. '):
                    # 移除列表标记
                    current_text_elements[0]["text_run"]["content"] = first_text[first_text.index('. ') + 2:]
                    blocks.append(self._create_ordered_block(current_text_elements))
                # 无序列表检测（- 或 • ）
                elif first_text and (first_text.startswith('- ') or first_text.startswith('• ')):
                    # 移除列表标记
                    current_text_elements[0]["text_run"]["content"] = first_text[2:]
                    blocks.append(self._create_bullet_block(current_text_elements))
                else:
                    blocks.append(self._create_text_block_from_elements(current_text_elements))
        
        # 3. 将第一个文本 Block 转换为三级标题（仅对非回复消息）
        # 3. 将第一个有效内容的文本 Block 转换为三级标题（仅对非回复消息）
        # 并且移除该标题之前的空 Block (由标签移除导致的空行)
        if not is_reply and len(blocks) > 1:
            header_block = blocks[0]
            body_blocks = blocks[1:]
            
            non_empty_index = -1
            
            # 寻找第一个非空文本块
            for i, block in enumerate(body_blocks):
                # 仅处理 Text Block
                if block.get("block_type") == 2:
                    elements = block.get("text", {}).get("elements", [])
                    has_content = False
                    for el in elements:
                        if el.get("text_run", {}).get("content", "").strip():
                            has_content = True
                            break
                    if has_content:
                        non_empty_index = i
                        break
                else:
                    # 遇到非文本块(如图片)，视作内容开始，停止跳过空行，但不转标题
                    non_empty_index = i
                    break
            
            if non_empty_index != -1:
                # 如果找到的是 Text Block，转为标题
                target_block = body_blocks[non_empty_index]
                if target_block.get("block_type") == 2:
                    target_block["block_type"] = 5 # heading3
                    target_block["heading3"] = target_block.pop("text")
                
                # 移除 non_empty_index 之前的空 blocks
                # 新的 blocks = Header + Body[non_empty_index:]
                blocks = [header_block] + body_blocks[non_empty_index:]
        
        # 4. 只有非回复消息才添加分割线
        if not is_reply:
            blocks.append(self._create_divider_block())
            
        return blocks

    def _parse_style(self, styles: List[str], un_styles: List[str]) -> Dict[str, bool]:
        """将飞书消息样式转换为 Docx 样式"""
        style_map = {}
        # Message styles: "bold", "underline", "lineThrough", "italic"
        # Docx styles: "bold", "underline", "strikethrough", "italic"
        
        if "bold" in styles: style_map["bold"] = True
        if "underline" in styles: style_map["underline"] = True
        if "lineThrough" in styles: style_map["strikethrough"] = True
        if "italic" in styles: style_map["italic"] = True
        
        return style_map

    def _create_text_run(self, content: str, style: Dict[str, bool] = None) -> Dict[str, Any]:
        """创建 Docx TextRun"""
        run = {
            "text_run": {
                "content": content,
            }
        }
        # 只有在有实际样式时才添加 text_element_style
        if style:
            run["text_run"]["text_element_style"] = style
        return run

    def _create_text_block_from_elements(self, elements: List[Dict]) -> Dict[str, Any]:
        """根据元素列表创建 Text Block"""
        return {
            "block_type": 2, # Text
            "text": {
                "elements": elements
            }
        }

    def _create_text_block(self, text: str) -> Dict[str, Any]:
        """创建简单文本 Block"""
        return self._create_text_block_from_elements([self._create_text_run(text)])

    def _create_heading_block(self, text: str, level: int = 1) -> Dict[str, Any]:
        """创建标题 Block (block_type 3-11 is H1-H9)"""
        # H1 = 3, H2 = 4, H3 = 5 ...
        block_type = 2 + level 
        
        # 动态构建键名 (heading1, heading2, ...)
        key_name = f"heading{level}"
        return {
            "block_type": block_type,
            key_name: {
                "elements": [self._create_text_run(text)]
            }
        }

    def _create_bullet_block(self, elements: List[Dict]) -> Dict[str, Any]:
        """创建无序列表 Block (block_type 12)"""
        return {
            "block_type": 12,
            "bullet": {
                "elements": elements
            }
        }

    def _create_ordered_block(self, elements: List[Dict]) -> Dict[str, Any]:
        """创建有序列表 Block (block_type 13)"""
        return {
            "block_type": 13,
            "ordered": {
                "elements": elements
            }
        }

    def _create_code_block(self, text: str, language: int = 1) -> Dict[str, Any]:
        """创建代码块 Block (block_type 14)"""
        return {
            "block_type": 14,
            "code": {
                "style": {
                    "language": language  # 1 = PlainText
                },
                "elements": [self._create_text_run(text)]
            }
        }

    def _create_quote_block(self, elements: List[Dict]) -> Dict[str, Any]:
        """创建引用 Block (block_type 15)"""
        return {
            "block_type": 15,
            "quote": {
                "elements": elements
            }
        }

    def _create_image_block(self, token: str) -> Dict[str, Any]:
        """创建图片 Block"""
        return {
            "block_type": 27, # Image
            "image": {
                "token": token
            }
        }

    def _create_divider_block(self) -> Dict[str, Any]:
        """创建分割线 Block"""
        return {
            "block_type": 22,  # Divider
            "divider": {}  # 飞书 API 要求必须有这个空对象
        }
