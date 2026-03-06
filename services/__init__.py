"""
服务层模块

包含飞书 Bot 的核心业务服务：
- FileUploadService: 统一文件上传服务
- PinService: Pin 消息处理服务
- UserService: 用户信息获取服务
- AsyncCardService: 异步卡片回复服务
- AnnouncementService: 公告识别服务

服务将在实现后自动可用。
"""

__all__ = [
    "FileUploadService",
    "PinService",
    "UserService",
    "AsyncCardService",
    "AnnouncementService",
]

# 动态导入已实现的服务
try:
    from .file_upload_service import FileUploadService
except ImportError:
    pass

try:
    from .pin_service import PinService
except ImportError:
    pass

try:
    from .user_service import UserService
except ImportError:
    pass

try:
    from .async_card_service import AsyncCardService
except ImportError:
    pass

try:
    from .announcement_service import AnnouncementService
except ImportError:
    pass
