"""
占位图生成器

为单聊异步回复生成占位图片，提示用户正在处理中
"""

import io
from typing import Optional
from PIL import Image, ImageDraw, ImageFont


def generate_placeholder(
    width: int = 720,
    height: int = 400,
    text: str = "正在生成卡片，请稍候...",
    bg_color: tuple = (240, 242, 245),
    text_color: tuple = (78, 89, 105)
) -> bytes:
    """
    生成占位图

    Args:
        width: 图片宽度（默认720）
        height: 图片高度（默认400）
        text: 提示文字
        bg_color: 背景颜色（RGB）
        text_color: 文字颜色（RGB）

    Returns:
        PNG格式的图片二进制数据

    Example:
        >>> img_data = generate_placeholder()
        >>> # 使用 img_data 发送图片消息
    """
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # 尝试获取中文字体
    font = _get_chinese_font(size=36)

    # 计算文字位置（居中）
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2

    # 绘制文字
    draw.text((x, y), text, fill=text_color, font=font)

    # 添加加载提示（底部小字）
    loading_font = _get_chinese_font(size=20)
    loading_text = "⏳ 完整内容将在后续消息中补充"
    loading_bbox = draw.textbbox((0, 0), loading_text, font=loading_font)
    loading_width = loading_bbox[2] - loading_bbox[0]
    loading_x = (width - loading_width) // 2
    draw.text((loading_x, y + 80), loading_text, fill=(150, 160, 170), font=loading_font)

    # 转换为 PNG 二进制
    img_io = io.BytesIO()
    img.save(img_io, format='PNG')
    return img_io.getvalue()


def _get_chinese_font(size: int = 20) -> ImageFont.ImageFont:
    """
    获取中文字体

    Args:
        size: 字体大小

    Returns:
        字体对象，失败返回默认字体
    """
    # 字体路径列表（按优先级）
    font_paths = [
        # Linux 常见字体
        "/usr/share/fonts/chinese/msyh.ttc",
        "/usr/share/fonts/chinese/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        # Windows 字体
        "C:\\Windows\\Fonts\\msyh.ttc",
        "C:\\Windows\\Fonts\\simhei.ttf",
        # macOS 字体
        "/System/Library/Fonts/PingFang.ttc",
        # 当前目录
        "msyh.ttc",
        "simhei.ttf"
    ]

    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue

    # 降级到默认字体
    return ImageFont.load_default()


def generate_with_theme(
    title: str = "文档处理中",
    message: str = "正在为您生成卡片摘要...",
    width: int = 720,
    height: int = 400
) -> bytes:
    """
    生成带主题的占位图

    Args:
        title: 标题文字
        message: 提示消息
        width: 图片宽度
        height: 图片高度

    Returns:
        PNG格式的图片二进制数据
    """
    img = Image.new('RGB', (width, height), (250, 252, 255))
    draw = ImageDraw.Draw(img)

    # 绘制卡片背景
    margin_x, margin_y = 35, 40
    card_rect = [
        margin_x, margin_y,
        width - margin_x, height - margin_y
    ]
    draw.rectangle(card_rect, fill=(255, 255, 255), outline=(220, 225, 230), width=2)

    # 绘制顶部装饰条
    header_height = 80
    header_rect = [
        card_rect[0] + 2, card_rect[1] + 2,
        card_rect[2] - 2, card_rect[1] + header_height
    ]
    draw.rectangle(header_rect, fill=(220, 235, 232))

    # 获取字体
    title_font = _get_chinese_font(32)
    msg_font = _get_chinese_font(24)
    loading_font = _get_chinese_font(18)

    # 绘制标题
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, header_rect[1] + 25), title, fill=(44, 62, 80), font=title_font)

    # 绘制消息
    msg_bbox = draw.textbbox((0, 0), message, font=msg_font)
    msg_width = msg_bbox[2] - msg_bbox[0]
    msg_x = (width - msg_width) // 2
    msg_y = header_rect[3] + 40
    draw.text((msg_x, msg_y), message, fill=(78, 89, 105), font=msg_font)

    # 绘制加载提示
    loading_text = "⏳ 完整内容即将送达..."
    loading_bbox = draw.textbbox((0, 0), loading_text, font=loading_font)
    loading_width = loading_bbox[2] - loading_bbox[0]
    loading_x = (width - loading_width) // 2
    draw.text((loading_x, msg_y + 60), loading_text, fill=(150, 160, 170), font=loading_font)

    # 转换为 PNG 二进制
    img_io = io.BytesIO()
    img.save(img_io, format='PNG')
    return img_io.getvalue()
