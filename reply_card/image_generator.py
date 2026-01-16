"""
图片生成器 - 将文档摘要生成为精美图片
"""

from PIL import Image, ImageDraw, ImageFont
import io

class DocImageGenerator:
    """文档摘要图片生成器"""
    
    # 图片尺寸配置
    WIDTH = 800
    HEIGHT = 600
    PADDING = 40
    
    # 颜色配置
    BG_COLOR = (255, 255, 255)  # 白色背景
    TITLE_COLOR = (31, 35, 41)  # 深灰色标题
    TEXT_COLOR = (75, 85, 99)   # 灰色正文
    ACCENT_COLOR = (59, 130, 246)  # 蓝色强调色
    
    def __init__(self):
        """初始化生成器"""
        pass
    
    def generate_doc_image(
        self, 
        title: str, 
        content: str, 
        doc_url: str = None  # 保留参数以兼容，不使用
    ) -> bytes:
        """
        生成文档摘要图片
        
        Args:
            title: 文档标题
            content: 文档内容预览（前300字）
            doc_url: 文档链接（保留参数，不使用）
            
        Returns:
            图片的二进制数据（PNG格式）
        """
        # 创建画布
        img = Image.new('RGB', (self.WIDTH, self.HEIGHT), self.BG_COLOR)
        draw = ImageDraw.Draw(img)
        
        # 尝试加载字体（如果失败则使用默认字体）
        try:
            title_font = ImageFont.truetype("msyh.ttc", 32)  # 微软雅黑
            content_font = ImageFont.truetype("msyh.ttc", 18)
            small_font = ImageFont.truetype("msyh.ttc", 14)
        except Exception:
            # 使用默认字体
            title_font = ImageFont.load_default()
            content_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        y_offset = self.PADDING
        
        # 1. 绘制顶部装饰条
        draw.rectangle(
            [(0, 0), (self.WIDTH, 8)],
            fill=self.ACCENT_COLOR
        )
        y_offset += 20
        
        # 2. 绘制图标和标题
        icon = "📄"
        draw.text(
            (self.PADDING, y_offset),
            icon,
            fill=self.TITLE_COLOR,
            font=title_font
        )
        
        # 标题（限制长度）
        display_title = title[:30] + "..." if len(title) > 30 else title
        draw.text(
            (self.PADDING + 50, y_offset),
            display_title,
            fill=self.TITLE_COLOR,
            font=title_font
        )
        y_offset += 60
        
        # 3. 绘制分割线
        draw.line(
            [(self.PADDING, y_offset), (self.WIDTH - self.PADDING, y_offset)],
            fill=(229, 231, 235),
            width=2
        )
        y_offset += 30
        
        # 4. 绘制内容预览标签
        draw.text(
            (self.PADDING, y_offset),
            "内容预览",
            fill=self.ACCENT_COLOR,
            font=content_font
        )
        y_offset += 35
        
        # 5. 分行显示内容（使用全宽）
        lines = self._wrap_text(content, 45)  # 增加每行字符数
        
        for line in lines[:12]:  # 最多显示12行
            draw.text(
                (self.PADDING, y_offset),
                line,
                fill=self.TEXT_COLOR,
                font=content_font
            )
            y_offset += 28
        
        # 6. 底部水印
        watermark = "由飞书 MCP 自动生成"
        draw.text(
            (self.PADDING, self.HEIGHT - 30),
            watermark,
            fill=(156, 163, 175),
            font=small_font
        )
        
        # 转换为字节流
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return img_byte_arr.getvalue()
    
    def _wrap_text(self, text: str, max_chars: int) -> list:
        """
        将长文本按指定字符数分行
        
        Args:
            text: 原始文本
            max_chars: 每行最大字符数
            
        Returns:
            分行后的文本列表
        """
        lines = []
        current_line = ""
        
        for char in text:
            if char == '\n':
                lines.append(current_line)
                current_line = ""
            elif len(current_line) >= max_chars:
                lines.append(current_line)
                current_line = char
            else:
                current_line += char
        
        if current_line:
            lines.append(current_line)
        
        return lines
