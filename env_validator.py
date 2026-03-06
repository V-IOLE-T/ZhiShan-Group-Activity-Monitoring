"""
环境变量验证模块

在程序启动时验证所有必需的环境变量，确保配置完整
"""

import os
from typing import Dict, List, Tuple
from dotenv import load_dotenv

load_dotenv()


class EnvironmentValidator:
    """环境变量验证器"""

    # 必需的环境变量
    REQUIRED_VARS: Dict[str, str] = {
        "APP_ID": "飞书应用ID",
        "APP_SECRET": "飞书应用密钥", 
        "CHAT_ID": "目标群组ID",
        "BITABLE_APP_TOKEN": "多维表格App Token",
        "BITABLE_TABLE_ID": "用户活跃度统计表ID",
    }

    # 可选的环境变量
    OPTIONAL_VARS: Dict[str, str] = {
        "ARCHIVE_TABLE_ID": "消息归档表ID（启用消息归档功能时需要）",
        "SUMMARY_TABLE_ID": "话题汇总表ID（启用话题汇总功能时需要）",
        "ANNOUNCEMENT_TAGS": "公告识别标签（逗号分隔，如 公告,通知）",
        "PIN_TABLE_ID": "Pin消息归档表ID（启用Pin监控功能时需要）",
        "PIN_MONITOR_INTERVAL": "Pin监控轮询间隔（秒）",
    }

    @classmethod
    def validate(cls, strict: bool = True) -> Tuple[bool, List[str]]:
        """
        验证环境变量配置

        Args:
            strict: 是否严格模式，True时缺少必需变量会抛出异常

        Returns:
            (是否通过, 错误消息列表)

        Raises:
            ValueError: 当strict=True且缺少必需变量时
        """
        missing_vars = []
        warnings = []

        # 检查必需变量
        for var, desc in cls.REQUIRED_VARS.items():
            value = os.getenv(var)
            if not value:
                missing_vars.append(f"  ❌ {var} ({desc})")
            elif value.strip() == "":
                missing_vars.append(f"  ❌ {var} ({desc}) - 值为空")
            else:
                print(f"  ✅ {var}: {value[:20]}...")

        if missing_vars:
            error_msg = "缺少必需的环境变量：\n" + "\n".join(missing_vars)
            error_msg += "\n\n请检查 .env 文件配置，参考 .env.example 模板"
            
            if strict:
                print(f"\n❌ 环境变量验证失败\n{error_msg}")
                raise ValueError(error_msg)
            else:
                return False, missing_vars

        print("\n✅ 所有必需的环境变量验证通过\n")

        # 检查可选变量
        print("📋 可选功能配置状态：")
        for var, desc in cls.OPTIONAL_VARS.items():
            value = os.getenv(var)
            if value:
                print(f"  ✅ {desc}: 已配置")
            else:
                print(f"  ⚪ {desc}: 未配置")
                warnings.append(f"  ⚪ {var} ({desc})")

        # 特殊验证：数值类型
        interval = os.getenv("PIN_MONITOR_INTERVAL", "30")
        try:
            interval_int = int(interval)
            if interval_int < 10 or interval_int > 3600:
                warning = f"  ⚠️ PIN_MONITOR_INTERVAL 建议设置在10-3600秒之间，当前值: {interval_int}"
                print(warning)
                warnings.append(warning)
        except ValueError:
            warning = f"  ⚠️ PIN_MONITOR_INTERVAL 格式错误，应为整数，当前值: {interval}"
            print(warning)
            warnings.append(warning)

        print("")
        return True, warnings

    @classmethod
    def validate_and_print(cls) -> None:
        """
        验证环境变量并打印详细信息
        
        这是推荐的使用方式，会在失败时抛出异常
        """
        print("\n" + "=" * 50)
        print("🔍 正在验证环境变量配置...")
        print("=" * 50)
        
        try:
            cls.validate(strict=True)
            print("✅ 环境变量验证完成，可以安全启动程序")
            print("=" * 50 + "\n")
        except ValueError as e:
            print("=" * 50)
            raise


# 便捷函数
def validate_environment() -> None:
    """
    验证环境变量（便捷函数）
    
    在程序启动时调用此函数确保配置完整
    
    Example:
        >>> from env_validator import validate_environment
        >>> validate_environment()
        
    Raises:
        ValueError: 当缺少必需的环境变量时
    """
    EnvironmentValidator.validate_and_print()


if __name__ == "__main__":
    # 测试验证器
    validate_environment()
