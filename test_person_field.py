"""
测试"人员"字段功能
"""
import os
from dotenv import load_dotenv
from auth import FeishuAuth
from storage import BitableStorage

load_dotenv()

def test_person_field():
    print("="*60)
    print("🧪 测试人员字段功能")
    print("="*60)
    
    # 初始化
    auth = FeishuAuth()
    auth.get_tenant_access_token()
    storage = BitableStorage(auth)
    
    # 测试数据
    test_user_id = "test_person_field_001"
    test_user_name = "测试人员字段"
    
    print(f"\n测试用户ID: {test_user_id}")
    print(f"测试用户名: {test_user_name}")
    
    # 创建测试记录
    print("\n正在创建测试记录...")
    try:
        metrics_delta = {
            "message_count": 1,
            "char_count": 5,
            "reply_received": 0,
            "mention_received": 0,
            "topic_initiated": 1
        }
        
        storage.update_or_create_record(
            user_id=test_user_id,
            user_name=test_user_name,
            metrics_delta=metrics_delta
        )
        
        print("\n" + "="*60)
        print("✅ 测试成功！")
        print("="*60)
        print("\n请检查你的飞书多维表格：")
        print("1. 应该有一条新记录")
        print("2. '用户ID' 列显示: test_person_field_001")
        print("3. '用户名称' 列显示: 测试人员字段")
        print("4. '人员' 列应该显示一个用户（如果该 open_id 存在）")
        print("   或显示为空（如果该 open_id 不存在，这是正常的）")
        print("\n💡 提示：")
        print("- 如果'人员'字段显示错误，请确保该字段类型为'人员'")
        print("- 真实使用时，会使用真实用户的 open_id，会正确显示用户信息")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n可能的原因：")
        print("1. 多维表格中没有'人员'字段")
        print("2. '人员'字段的类型不是'人员'类型")
        print("3. 应用没有多维表格的写入权限")
        print("\n解决方案：")
        print("1. 运行 'python check_table_fields.py' 检查字段配置")
        print("2. 参考 '添加人员字段说明.md' 正确添加字段")

if __name__ == "__main__":
    test_person_field()
