#!/usr/bin/env python3
"""
飞书活跃度监测系统 - 主入口
Author: V-IOLE-T/ZhiShan-Group-Activity-Monitoring
Version: 4.3

使用方法:
    python main.py

功能:
    - 实时监听群消息
    - 统计用户活跃度
    - Pin 消息周报 (每周一 9:00)
    - 文档归档 (仅带标签消息)
    - 点赞统计
    - 单聊智能回复
"""
import sys
import os
from pathlib import Path

# 确保可以导入项目模块
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置配置文件路径
os.environ.setdefault('ENV_FILE_PATH', str(project_root / 'config' / '.env'))

def main():
    """主入口函数"""
    print("=" * 60)
    print("🚀 飞书活跃度监测系统 V4.3")
    print("=" * 60)
    print()
    
    # 导入并运行主监听器
    from long_connection_listener import main as listener_main
    
    try:
        listener_main()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，程序退出")
    except Exception as e:
        print(f"\n\n❌ 程序异常退出: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
