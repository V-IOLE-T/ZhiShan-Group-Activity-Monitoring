"""
日志系统配置
提供统一的日志记录功能，支持控制台和文件输出
"""
import logging
import os
from datetime import datetime
from pathlib import Path


# 创建logs目录
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    配置并返回一个日志记录器

    Args:
        name: 日志记录器名称，通常使用模块名 __name__
        level: 日志级别，可选 "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"

    Returns:
        配置好的日志记录器

    Example:
        >>> logger = setup_logger(__name__)
        >>> logger.info("程序启动")
        >>> logger.error("发生错误", exc_info=True)
    """
    logger = logging.getLogger(name)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 设置日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器 - 按日期分割日志文件
    log_file = LOGS_DIR / f"feishu_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 错误日志单独记录
    error_log_file = LOGS_DIR / f"feishu_error_{datetime.now().strftime('%Y%m%d')}.log"
    error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    # 防止日志向上传播到根记录器
    logger.propagate = False

    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志记录器（简化版）

    Args:
        name: 日志记录器名称，默认使用 "feishu"

    Returns:
        日志记录器

    Example:
        >>> from logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("这是一条信息")
    """
    if name is None:
        name = "feishu"
    return setup_logger(name)


# 预配置的日志记录器
default_logger = setup_logger("feishu")


def cleanup_old_logs(days: int = 7):
    """
    清理指定天数之前的日志文件

    Args:
        days: 保留最近N天的日志，默认7天

    Example:
        >>> cleanup_old_logs(7)  # 清理7天前的日志
    """
    import time

    cutoff_time = time.time() - (days * 86400)

    for log_file in LOGS_DIR.glob("feishu_*.log"):
        if log_file.stat().st_mtime < cutoff_time:
            try:
                log_file.unlink()
                default_logger.info(f"已清理旧日志文件: {log_file.name}")
            except Exception as e:
                default_logger.error(f"清理日志文件失败 {log_file.name}: {e}")


# 使用示例
if __name__ == "__main__":
    # 测试日志系统
    logger = get_logger("test")

    logger.debug("这是一条调试信息")
    logger.info("这是一条普通信息")
    logger.warning("这是一条警告信息")
    logger.error("这是一条错误信息")
    logger.critical("这是一条严重错误信息")

    # 测试异常记录
    try:
        1 / 0
    except Exception as e:
        logger.error("发生异常", exc_info=True)

    print(f"\n日志已写入: {LOGS_DIR}")
