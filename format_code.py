"""
代码格式化工具脚本

运行Black、isort和flake8对代码进行格式化和检查
"""
import subprocess
import sys


def run_command(command, description):
    """运行命令并显示结果"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")

    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode


def main():
    """主函数"""
    print("🚀 开始代码格式化和检查...")

    # 检查是否安装了所需工具
    print("\n📦 检查所需工具...")
    required_tools = ['black', 'isort', 'flake8']
    missing_tools = []

    for tool in required_tools:
        check_result = subprocess.run(
            f"{tool} --version",
            shell=True,
            capture_output=True
        )
        if check_result.returncode != 0:
            missing_tools.append(tool)

    if missing_tools:
        print(f"\n❌ 缺少以下工具: {', '.join(missing_tools)}")
        print("\n请运行以下命令安装:")
        print(f"pip install {' '.join(missing_tools)}")
        return 1

    print("✅ 所有工具已安装")

    # 运行isort整理导入
    code1 = run_command(
        "isort .",
        "使用isort整理导入语句"
    )

    # 运行Black格式化
    code2 = run_command(
        "black .",
        "使用Black格式化代码"
    )

    # 运行flake8检查
    code3 = run_command(
        "flake8 .",
        "使用flake8检查代码质量"
    )

    # 运行mypy类型检查（可选）
    print(f"\n{'='*60}")
    print("🔍 运行mypy类型检查（可选）")
    print(f"{'='*60}")
    mypy_result = subprocess.run(
        "mypy --version",
        shell=True,
        capture_output=True
    )

    if mypy_result.returncode == 0:
        code4 = run_command(
            "mypy auth.py collector.py rate_limiter.py utils.py logger.py",
            "使用mypy检查类型提示"
        )
    else:
        print("⚠️ mypy未安装，跳过类型检查")
        print("提示: pip install mypy")
        code4 = 0

    # 汇总结果
    print(f"\n{'='*60}")
    print("📊 格式化结果汇总")
    print(f"{'='*60}")
    print(f"isort:  {'✅ 成功' if code1 == 0 else '❌ 失败'}")
    print(f"black:  {'✅ 成功' if code2 == 0 else '❌ 失败'}")
    print(f"flake8: {'✅ 成功' if code3 == 0 else '⚠️ 发现问题'}")

    if code3 != 0:
        print("\n💡 提示: flake8发现了一些代码风格问题，请查看上面的输出")

    print("\n✨ 代码格式化完成！")

    return 0


if __name__ == '__main__':
    sys.exit(main())
