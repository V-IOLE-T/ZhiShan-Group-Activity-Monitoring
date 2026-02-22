"""
跨平台定时任务调度脚本
支持 Windows 和 Linux 系统
"""
import os
import sys
import platform
import subprocess
from pathlib import Path

def get_python_path():
    """获取 Python 解释器路径"""
    # 优先使用虚拟环境的 Python
    venv_path = Path(__file__).parent / "venv"
    
    if platform.system() == "Windows":
        python_exe = venv_path / "Scripts" / "python.exe"
        if python_exe.exists():
            return str(python_exe)
        return sys.executable
    else:  # Linux/Mac
        python_exe = venv_path / "bin" / "python"
        if python_exe.exists():
            return str(python_exe)
        return sys.executable


def get_script_path():
    """获取 pin_weekly_report.py 的绝对路径"""
    script_dir = Path(__file__).parent
    return str(script_dir / "pin_weekly_report.py")


def setup_windows_task():
    """设置 Windows 计划任务"""
    python_path = get_python_path()
    script_path = get_script_path()
    
    task_name = "FeishuPinWeeklyReport"
    
    # 删除已存在的任务
    print(f"🔍 检查是否存在旧任务...")
    subprocess.run(
        f'schtasks /delete /tn "{task_name}" /f',
        shell=True,
        capture_output=True
    )
    
    # 创建新任务 (每周一早上 9:00)
    print(f"📅 创建 Windows 计划任务...")
    command = f'schtasks /create /tn "{task_name}" /tr "\\"{python_path}\\" \\"{script_path}\\"" /sc weekly /d MON /st 09:00 /f'
    
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ Windows 计划任务创建成功!")
        print(f"   任务名: {task_name}")
        print(f"   执行时间: 每周一 09:00")
        print(f"   Python: {python_path}")
        print(f"   脚本: {script_path}")
    else:
        print(f"❌ 创建失败:")
        print(result.stderr)


def setup_linux_cron():
    """设置 Linux crontab"""
    python_path = get_python_path()
    script_path = get_script_path()
    log_path = Path(__file__).parent / "pin_weekly.log"
    
    # Cron 表达式: 每周一 9:00
    cron_line = f"0 9 * * 1 {python_path} {script_path} >> {log_path} 2>&1"
    
    print(f"📅 配置 Linux crontab...")
    print(f"   Cron 表达式: 0 9 * * 1 (每周一 09:00)")
    print(f"   Python: {python_path}")
    print(f"   脚本: {script_path}")
    print(f"   日志: {log_path}")
    print()
    print("请手动添加以下内容到 crontab:")
    print("-" * 60)
    print(cron_line)
    print("-" * 60)
    print()
    print("步骤:")
    print("  1. 运行命令: crontab -e")
    print("  2. 添加上述行到文件末尾")
    print("  3. 保存并退出")


def test_script():
    """测试运行脚本"""
    python_path = get_python_path()
    script_path = get_script_path()
    
    print(f"\n🧪 测试运行 Pin 周报脚本...")
    print(f"   命令: {python_path} {script_path}")
    print("-" * 60)
    
    result = subprocess.run(
        [python_path, script_path],
        capture_output=False,
        text=True
    )
    
    if result.returncode == 0:
        print("-" * 60)
        print("✅ 脚本运行成功!")
    else:
        print("-" * 60)
        print(f"❌ 脚本运行失败 (返回码: {result.returncode})")


def main():
    """主函数"""
    print("=" * 60)
    print("📌 Pin 周报定时任务配置工具")
    print("=" * 60)
    print()
    
    system = platform.system()
    print(f"🖥️  当前系统: {system}")
    print()
    
    # 选项菜单
    print("请选择操作:")
    print("  1. 设置定时任务")
    print("  2. 测试运行脚本")
    print("  3. 退出")
    print()
    
    choice = input("请输入选项 (1-3): ").strip()
    
    if choice == "1":
        if system == "Windows":
            setup_windows_task()
        elif system == "Linux" or system == "Darwin":
            setup_linux_cron()
        else:
            print(f"❌ 不支持的系统: {system}")
    
    elif choice == "2":
        test_script()
    
    elif choice == "3":
        print("👋 退出")
    
    else:
        print("❌ 无效选项")


if __name__ == "__main__":
    main()
