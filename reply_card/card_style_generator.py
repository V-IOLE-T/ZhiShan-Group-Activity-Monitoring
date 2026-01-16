import io
import os
import re
import json
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from pilmoji import Pilmoji

class CardStyleImageGenerator:
    WIDTH = 720
    BG_COLOR = (240, 242, 245)
    CARD_BG_COLOR = (255, 255, 255)
    HEADER_BG_COLOR = (220, 235, 232)
    TITLE_COLOR = (44, 62, 80)
    TEXT_COLOR = (78, 89, 105)
    
    # 路径请确保在服务器上正确
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ICON_PATH = os.path.join(BASE_DIR, "至善者联盟.jpg")
    LEFT_IMAGE_PATH = os.path.join(BASE_DIR, "云端中心.png")
    RIGHT_IMAGE_PATH = os.path.join(BASE_DIR, "至善者联盟下单链接.png")

    def get_font(self, size, bold=False):
        # 字体路径列表
        font_paths = [
            "/usr/share/fonts/chinese/msyhbd.ttc" if bold else "/usr/share/fonts/chinese/msyh.ttc",
            "/usr/share/fonts/chinese/msyh.ttc",
            "/usr/share/fonts/chinese/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "msyh.ttc", "simhei.ttf"
        ]
        for path in font_paths:
            try:
                # 如果使用 Linux 字体，稍微加大 2 像素补偿
                final_size = size + (2 if "wqy" in path else 0)
                return ImageFont.truetype(path, final_size)
            except: continue
        return ImageFont.load_default()

    def generate_card_image(self, title: str, content: str) -> bytes:
        clean_content = self._clean_markdown(content)
        # 这里的 22 是每行字数，可以根据需要微调
        raw_lines = self._wrap_text(clean_content, 22)
        
        limit = min(15, max(1, int(len(raw_lines) * 0.7)))
        display_lines = raw_lines[:limit]
        
        header_h = 130 if title else 0
        line_height = 50 # 适中的行高
        content_margin = 80
        bottom_area_h = 420 
        card_margin_y = 50
        
        calculated_content_h = len(display_lines) * line_height
        total_height = header_h + calculated_content_h + content_margin + bottom_area_h + (card_margin_y * 2)
        
        img = Image.new('RGB', (self.WIDTH, total_height), self.BG_COLOR)
        draw = ImageDraw.Draw(img)
        
        # 1. 绘制带有阴影效果的白色卡片
        card_margin_x = 35
        card_rect = [card_margin_x, card_margin_y, self.WIDTH - card_margin_x, total_height - card_margin_y]
        for i in range(12):
            c = 230 + i
            if c > 255: c = 255
            draw.rectangle([card_rect[0]+i, card_rect[1]+i, card_rect[2]+i, card_rect[3]+i], outline=(c, c, c), width=1)
        draw.rectangle(card_rect, fill=self.CARD_BG_COLOR)

        title_font = self.get_font(32, bold=True)
        content_font = self.get_font(26)
        footer_font = self.get_font(20)

        # 2. 顶部 Logo + 标题
        if header_h > 0:
            header_rect = [card_rect[0], card_rect[1], card_rect[2], card_rect[1] + header_h]
            draw.rectangle(header_rect, fill=self.HEADER_BG_COLOR)
            
            cur_x = card_rect[0] + 40
            # 绘制圆形图标
            if os.path.exists(self.ICON_PATH):
                try:
                    icon = Image.open(self.ICON_PATH).convert("RGBA").resize((80, 80), Image.Resampling.LANCZOS)
                    img.paste(icon, (cur_x, card_rect[1] + (header_h - 80)//2), icon)
                    cur_x += 100
                except: pass
            
            with Pilmoji(img) as pilmoji:
                pilmoji.text((cur_x, card_rect[1] + 45), title[:20], fill=self.TITLE_COLOR, font=title_font)

        # 3. 正文渲染
        y_offset = card_rect[1] + header_h + 45
        with Pilmoji(img) as pilmoji:
            for i, line in enumerate(display_lines):
                draw_color = self.TEXT_COLOR
                draw_text = line
                
                # 特殊处理：最后一两行变淡并添加省略号
                if i == len(display_lines) - 1:
                    draw_color = (209, 213, 219)
                    # 截断部分文字并添加省略号，增加引流感
                    if len(line) > 18:
                        draw_text = line[:18] + "......"
                    else:
                        draw_text = line + "......"
                elif i == len(display_lines) - 2:
                    draw_color = (156, 163, 175)
                
                pilmoji.text((card_rect[0] + 45, y_offset), draw_text, fill=draw_color, font=content_font)
                y_offset += line_height

        # 4. 引流提示
        hint_text = "— 内容过长，仅展示部分资料 —"
        hint_color = (90, 145, 135)
        bbox = draw.textbbox((0, 0), hint_text, font=footer_font)
        draw.text(((self.WIDTH - (bbox[2]-bbox[0]))//2, y_offset + 30), hint_text, fill=hint_color, font=footer_font)

        # 5. 底部双图 (还原核心排版)
        img_area_y = total_height - card_margin_y - 350
        self._paste_aspect_fit(img, self.LEFT_IMAGE_PATH, (card_rect[0] + 45, img_area_y), (400, 300))
        self._paste_aspect_fit(img, self.RIGHT_IMAGE_PATH, (self.WIDTH - 250, img_area_y), (180, 180))

        # 6. 页脚
        draw.text((self.WIDTH//2 - 50, total_height - 95), "至善者联盟", fill=hint_color, font=footer_font)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def _paste_aspect_fit(self, base_img, path, pos, max_size):
        if not os.path.exists(path): return
        try:
            p_img = Image.open(path).convert("RGBA")
            w, h = p_img.size
            ratio = min(max_size[0]/w, max_size[1]/h)
            new_size = (int(w * ratio), int(h * ratio))
            p_img = p_img.resize(new_size, Image.Resampling.LANCZOS)
            base_img.paste(p_img, pos, p_img)
        except: pass

    def _clean_markdown(self, text):
        return re.sub(r'[*#]', '', text)

    def _wrap_text(self, text, max_chars):
        lines = []
        for p in text.split('\n'):
            if not p:
                lines.append("")
                continue
            for i in range(0, len(p), max_chars):
                lines.append(p[i:i+max_chars])
        return lines