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
        "ARCHIVE_TABLE_ID": "公告归档表ID（启用公告专表写入时需要）",
        "ANNOUNCEMENT_TAGS": "公告识别标签（可选覆盖，默认值：公告,通知）",
        "PIN_TABLE_ID": "Pin归档表ID（启用每周 Pin 审计写表时需要）",
        "ARCHIVE_STATS_TABLE_ID": "月度归档历史表ID（启用月度归档时需要）",
    }

    DEFAULT_ANNOUNCEMENT_TAGS = "公告,通知"

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
            if var == "ANNOUNCEMENT_TAGS":
                if value:
                    normalized_tags = ",".join(
                        part.strip() for part in value.split(",") if part.strip()
                    )
                    print(f"  ✅ {desc}: {normalized_tags}")
                else:
                    print(
                        f"  ⚪ {desc}: 未配置，将使用默认值：{cls.DEFAULT_ANNOUNCEMENT_TAGS}"
                    )
                continue

            if value:
                print(f"  ✅ {desc}: 已配置")
            else:
                print(f"  ⚪ {desc}: 未配置")
                warnings.append(f"  ⚪ {var} ({desc})")

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
