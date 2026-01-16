"""
改进的日志管理模块

添加日志轮转功能，防止日志文件无限增长占满磁盘空间
"""

import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path


class LoggerConfig:
    """日志配置类"""
    
    # 日志目录
    LOG_DIR = "logs"
    
    # 日志文件名
    LOG_FILE = "activity_monitor.log"
    
    # 按大小轮转配置
    MAX_BYTES = 10 * 1024 * 1024  # 10MB per file
    BACKUP_COUNT = 5  # Keep 5 backup files
    
    # 按时间轮转配置（如果选择使用）
    WHEN = 'midnight'  # 每天午夜轮转
    INTERVAL = 1  # 每1天
    BACKUP_COUNT_TIME = 30  # 保留30天
    
    # 日志级别
    LOG_LEVEL = logging.INFO
    
    # 日志格式
    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def get_logger(name: str, use_rotation: bool = True, rotation_type: str = 'size') -> logging.Logger:
    """
    获取配置好的日志记录器
    
    Args:
        name: 日志记录器名称，通常使用 __name__
        use_rotation: 是否使用日志轮转，默认True
        rotation_type: 轮转类型，'size'(按大小) 或 'time'(按时间)，默认'size'
    
    Returns:
        配置好的日志记录器实例
        
    Example:
        >>> from logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("这是一条日志")
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    logger.setLevel(LoggerConfig.LOG_LEVEL)
    
    # 确保日志目录存在
    log_dir = Path(LoggerConfig.LOG_DIR)
    log_dir.mkdir(exist_ok=True)
    
    log_file_path = log_dir / LoggerConfig.LOG_FILE
    
    # 创建格式化器
    formatter = logging.Formatter(
        fmt=LoggerConfig.FORMAT,
        datefmt=LoggerConfig.DATE_FORMAT
    )
    
    # 根据配置选择合适的handler
    if use_rotation:
        if rotation_type == 'size':
            # 按大小轮转：适合日志量大的场景
            file_handler = RotatingFileHandler(
                filename=str(log_file_path),
                maxBytes=LoggerConfig.MAX_BYTES,
                backupCount=LoggerConfig.BACKUP_COUNT,
                encoding='utf-8'
            )
            logger.info(f"使用日志轮转：按大小 (最大{LoggerConfig.MAX_BYTES / 1024 / 1024}MB, 保留{LoggerConfig.BACKUP_COUNT}个备份)")
        elif rotation_type == 'time':
            # 按时间轮转：适合需要按天归档的场景
            file_handler = TimedRotatingFileHandler(
                filename=str(log_file_path),
                when=LoggerConfig.WHEN,
                interval=LoggerConfig.INTERVAL,
                backupCount=LoggerConfig.BACKUP_COUNT_TIME,
                encoding='utf-8'
            )
            logger.info(f"使用日志轮转：按时间 (每{LoggerConfig.WHEN}, 保留{LoggerConfig.BACKUP_COUNT_TIME}天)")
        else:
            raise ValueError(f"不支持的轮转类型: {rotation_type}，请使用 'size' 或 'time'")
    else:
        # 不使用轮转（不推荐用于生产环境）
        file_handler = logging.FileHandler(
            filename=str(log_file_path),
            encoding='utf-8'
        )
    
    file_handler.setLevel(LoggerConfig.LOG_LEVEL)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 同时输出到控制台（可选）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


def get_file_logger(name: str) -> logging.Logger:
    """
    仅记录到文件的日志记录器（不输出到控制台）
    
    Args:
        name: 日志记录器名称
        
    Returns:
        配置好的日志记录器实例
    """
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(LoggerConfig.LOG_LEVEL)
    
    log_dir = Path(LoggerConfig.LOG_DIR)
    log_dir.mkdir(exist_ok=True)
    
    log_file_path = log_dir / LoggerConfig.LOG_FILE
    
    formatter = logging.Formatter(
        fmt=LoggerConfig.FORMAT,
        datefmt=LoggerConfig.DATE_FORMAT
    )
    
    file_handler = RotatingFileHandler(
        filename=str(log_file_path),
        maxBytes=LoggerConfig.MAX_BYTES,
        backupCount=LoggerConfig.BACKUP_COUNT,
        encoding='utf-8'
    )
    
    file_handler.setLevel(LoggerConfig.LOG_LEVEL)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


def cleanup_old_logs(days: int = 30) -> None:
    """
    清理指定天数之前的日志文件
    
    Args:
        days: 保留最近多少天的日志，默认30天
    """
    import time
    from datetime import datetime, timedelta
    
    log_dir = Path(LoggerConfig.LOG_DIR)
    if not log_dir.exists():
        return
    
    cutoff_time = time.time() - (days * 24 * 60 * 60)
    deleted_count = 0
    
    for log_file in log_dir.glob("*.log*"):
        if log_file.stat().st_mtime < cutoff_time:
            try:
                log_file.unlink()
                deleted_count += 1
                print(f"✅ 已删除旧日志: {log_file.name}")
            except Exception as e:
                print(f"❌ 删除日志失败 {log_file.name}: {e}")
    
    if deleted_count > 0:
        print(f"✅ 共清理 {deleted_count} 个旧日志文件")
    else:
        print(f"✅ 没有需要清理的旧日志文件（保留{days}天内的日志）")


# 全局日志记录器实例（向后兼容）
logger = get_logger(__name__)


if __name__ == "__main__":
    # 测试日志记录器
    test_logger = get_logger("test")
    test_logger.info("这是一条测试日志")
    test_logger.warning("这是一条警告日志")
    test_logger.error("这是一条错误日志")
    
    print("\n" + "=" * 50)
    print("日志测试完成，请检查 logs/activity_monitor.log")
    print("=" * 50)
