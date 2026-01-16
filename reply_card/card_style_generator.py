"""
卡片样式图片生成器 - 高级美化版 (等比缩放 + 阴影效果)
"""

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from pilmoji import Pilmoji
import io
import os
import re

class CardStyleImageGenerator:
    """
    针对手机优化且具备高级审美的卡片生成器
    """
    
    # 图片尺寸配置
    WIDTH = 720
    # HEIGHT = 1280  # 废弃固定高度
    
    # 颜色配置
    BG_COLOR = (240, 242, 245)
    CARD_BG_COLOR = (255, 255, 255)
    HEADER_BG_COLOR = (220, 235, 232)
    TITLE_COLOR = (29, 33, 41)
    TEXT_COLOR = (78, 89, 105)
    
    # 资源路径
    ICON_PATH = "reply_card/至善者联盟.jpg"
    LEFT_IMAGE_PATH = "reply_card/云端中心.png"
    RIGHT_IMAGE_PATH = "reply_card/至善者联盟下单链接.png"
    
    def __init__(self):
        pass

    def generate_card_image(self, title: str, content: str) -> bytes:
        """生成支持内容无限生长的手机长图"""
        # 0. 准备工作
        clean_content = self._clean_markdown(content)
        raw_lines = self._wrap_text(clean_content, 22)
        
        # 1. 动态计算展示行数 (实现“无论多长都只展示一部分”)
        total_raw_lines = len(raw_lines)
        
        # 核心逻辑：
        # 如果非常短(少于5行)，展示其 60%
        # 如果中等长度，展示其 70%
        # 无论多长，最高封顶 15 行，保证“引流感”
        if total_raw_lines <= 5:
            limit = max(1, int(total_raw_lines * 0.6))
        else:
            limit = min(15, int(total_raw_lines * 0.7))
            
        display_lines = raw_lines[:limit] 
        
        # 2. 动态计算高度
        header_h = 130 if title else 0 # 如果没有标题，则不显示页眉
        line_height = 46
        content_margin = 80 # 上下边距
        bottom_area_h = 420 
        card_margin_y = 50
        
        calculated_content_h = len(display_lines) * line_height
        dynamic_card_h = header_h + calculated_content_h + content_margin + bottom_area_h
        total_height = dynamic_card_h + card_margin_y * 2
        
        # 2. 初始化画布
        img = Image.new('RGB', (self.WIDTH, total_height), self.BG_COLOR)
        draw = ImageDraw.Draw(img)
        
        # 绘制背景卡片
        card_margin_x = 35
        card_rect = [card_margin_x, card_margin_y, self.WIDTH - card_margin_x, total_height - card_margin_y]
        
        # 模拟阴影
        for i in range(12):
            color = 230 + i
            if color > 255: color = 255
            draw.rectangle([card_rect[0]+i, card_rect[1]+i, card_rect[2]+i, card_rect[3]+i], outline=(color, color, color), width=1)
        
        draw.rectangle(card_rect, fill=self.CARD_BG_COLOR)
        
        # 3. 加载字体 (强化清晰度：使用加粗版微软雅黑)
        def get_font(size, bold=False):
            font_names = ["msyhbd.ttc" if bold else "msyh.ttc", "msyh.ttc", "simhei.ttf"]
            for name in font_names:
                try:
                    return ImageFont.truetype(name, size)
                except (OSError, IOError):
                    continue
            return ImageFont.load_default()

        title_font = get_font(32, bold=False) # 标题不加粗
        content_font = get_font(26)
        footer_font = get_font(20)
        
        if header_h > 0:
            # 4. 标题栏渲染
            header_rect = [card_rect[0], card_rect[1], card_rect[2], card_rect[1] + header_h]
            draw.rectangle(header_rect, fill=self.HEADER_BG_COLOR)
            
            cur_x = card_rect[0] + 40
            try:
                if os.path.exists(self.ICON_PATH):
                    icon = Image.open(self.ICON_PATH).convert("RGBA")
                    icon_size = 80
                    icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                    img.paste(icon, (cur_x, card_rect[1] + (header_h - icon_size)//2), icon)
                    cur_x += icon_size + 20 
            except (FileNotFoundError, UnidentifiedImageError, OSError):
                pass
            
            # 标题文字 - 【基于像素宽度的动态折行算法】
            # 提高对比度：使用深石板色，确保清晰易读
            title_color = (44, 62, 80) 
            title_line_height = 42
            
            # 计算可用宽度（边缘间距缩减至 25px，更靠近边缘）
            max_title_w = card_rect[2] - cur_x - 25
            
            title_lines = []
            current_line = ""
            for char in title:
                # 动态测量当前行像素宽度
                if draw.textlength(current_line + char, font=title_font) <= max_title_w:
                    current_line += char
                else:
                    title_lines.append(current_line)
                    current_line = char
            if current_line:
                title_lines.append(current_line)
                
            # 动态垂直居中
            total_title_h = len(title_lines) * title_line_height
            title_start_y = card_rect[1] + (header_h - total_title_h) // 2
            
            # 使用 Pilmoji 渲染
            with Pilmoji(img) as pilmoji:
                for idx, line in enumerate(title_lines):
                    ly = title_start_y + (idx * title_line_height)
                    pilmoji.text(
                        (cur_x, ly), 
                        line, 
                        fill=title_color, 
                        font=title_font,
                        emoji_scale_factor=0.85,
                        emoji_position_offset=(0, 5) # 适配加粗字体的基线
                    )
        
        # 5. 正文渲染 (渐变引流效果) - 使用 Pilmoji
        y_offset = card_rect[1] + header_h + 45
        FADE_COLOR_1 = (156, 163, 175)
        FADE_COLOR_2 = (209, 213, 219)
        
        with Pilmoji(img) as pilmoji:
            for i, line in enumerate(display_lines):
                is_last = (i == len(display_lines) - 1)
                is_second_last = (i == len(display_lines) - 2)
                
                draw_color = self.TEXT_COLOR
                draw_text = line
                
                if is_last:
                    draw_color = FADE_COLOR_2
                    draw_text = line[:18] + "......"
                elif is_second_last:
                    draw_color = FADE_COLOR_1
                    
                # 使用 Pilmoji 渲染支持 Emoji，调整间距
                pilmoji.text(
                    (card_rect[0] + 45, y_offset), 
                    draw_text, 
                    fill=draw_color, 
                    font=content_font,
                    emoji_scale_factor=0.90,  # 正文 Emoji 适度缩小
                    emoji_position_offset=(0, 2)  # 向下偏移2px对齐
                )
                y_offset += line_height

        # 6. 引流提示语 (优化对比度与清晰度)
        y_offset += 30
        hint_text = "— 内容过长，仅展示部分资料 —"
        # 使用深青色以保证白底清晰度，保持色系统一
        hint_color = (90, 145, 135) 
        
        try:
            hint_font = ImageFont.truetype("msyh.ttc", 22)
        except (OSError, IOError):
            hint_font = footer_font
            
        bbox = draw.textbbox((0, 0), hint_text, font=hint_font)
        hint_w = bbox[2] - bbox[0]
        draw.text(((self.WIDTH - hint_w) // 2, y_offset), hint_text, fill=hint_color, font=hint_font)
        
        # 7. 底部固定图片区域
        img_area_y = total_height - card_margin_y - 350
        inner_w = (card_rect[2] - card_rect[0]) - 90
        left_max_w = int(inner_w * 0.62)
        right_max_w = inner_w - left_max_w - 25
        max_h = 300
        
        self._paste_aspect_fit(img, self.LEFT_IMAGE_PATH, (card_rect[0] + 45, img_area_y), (left_max_w, max_h))
        self._paste_aspect_fit(img, self.RIGHT_IMAGE_PATH, (card_rect[0] + 45 + left_max_w + 25, img_area_y), (right_max_w, max_h))
        
        # 8. 页脚 (绝对居中)
        footer_text = "至善者联盟"
        theme_color = (90, 145, 135)
        try:
            # 使用 textbbox 获取文本的精确宽度
            bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
            footer_w = bbox[2] - bbox[0]
            draw.text(((self.WIDTH - footer_w) // 2, total_height - 95), footer_text, fill=theme_color, font=footer_font)
        except AttributeError:
            # 兼容旧版本 Pillow（textbbox 方法不存在）
            draw.text((self.WIDTH // 2 - 50, total_height - 95), footer_text, fill=theme_color, font=footer_font)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def _paste_aspect_fit(self, base_img, path, pos, max_size):
        """等比缩放并粘贴图片"""
        if not os.path.exists(path): return
        try:
            p_img = Image.open(path).convert("RGBA")
            w, h = p_img.size
            ratio = min(max_size[0]/w, max_size[1]/h)
            new_size = (int(w * ratio), int(h * ratio))
            
            # 使用高质量重采样
            p_img = p_img.resize(new_size, Image.Resampling.LANCZOS)
            
            # 在预留区域内居中显示
            offset_x = (max_size[0] - new_size[0]) // 2
            offset_y = (max_size[1] - new_size[1]) // 2
            
            base_img.paste(p_img, (pos[0] + offset_x, pos[1] + offset_y), p_img)
        except (FileNotFoundError, UnidentifiedImageError, OSError):
            # 图片文件不存在或无法识别时静默跳过
            pass

    def _clean_markdown(self, text: str) -> str:
        """移除 Markdown 干扰符"""
        text = text.replace("**", "")
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        return text

    def _wrap_text(self, text: str, max_chars: int) -> list:
        """支持手动换行与自动折行"""
        lines = []
        for p in text.split('\n'):
            if not p:
                lines.append("")
                continue
            # 单行过长则折行
            for i in range(0, len(p), max_chars):
                lines.append(p[i:i+max_chars])
        return lines
