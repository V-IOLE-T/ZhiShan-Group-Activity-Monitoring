"""
Bitable 连接诊断工具
用于检查多维表格的配置和权限
"""
import os
from dotenv import load_dotenv
from auth import FeishuAuth
from storage import BitableStorage

load_dotenv()

def test_bitable_connection():
    print("="*60)
    print("🔍 开始诊断 Bitable 配置...")
    print("="*60)
    
    # 1. 检查环境变量
    print("\n[步骤 1] 检查环境变量")
    app_id = os.getenv('APP_ID')
    app_secret = os.getenv('APP_SECRET')
    bitable_app_token = os.getenv('BITABLE_APP_TOKEN')
    bitable_table_id = os.getenv('BITABLE_TABLE_ID')
    chat_id = os.getenv('CHAT_ID')
    
    print(f"  APP_ID: {'✅ 已配置' if app_id else '❌ 未配置'}")
    print(f"  APP_SECRET: {'✅ 已配置' if app_secret else '❌ 未配置'}")
    print(f"  BITABLE_APP_TOKEN: {'✅ 已配置' if bitable_app_token else '❌ 未配置'}")
    print(f"  BITABLE_TABLE_ID: {'✅ 已配置' if bitable_table_id else '❌ 未配置'}")
    print(f"  CHAT_ID: {'✅ 已配置' if chat_id else '❌ 未配置'}")
    
    if not all([app_id, app_secret, bitable_app_token, bitable_table_id]):
        print("\n❌ 环境变量配置不完整，无法继续测试")
        return
    
    # 2. 测试认证
    print("\n[步骤 2] 测试飞书认证")
    try:
        auth = FeishuAuth()
        token = auth.get_tenant_access_token()
        print(f"  ✅ 认证成功")
        print(f"  Token (前20字符): {token[:20]}...")
    except Exception as e:
        print(f"  ❌ 认证失败: {e}")
        return
    
    # 3. 测试查询记录
    print("\n[步骤 3] 测试查询记录")
    try:
        storage = BitableStorage(auth)
        from datetime import datetime
        month = datetime.now().strftime("%Y-%m")
        
        # 使用一个测试用户 ID
        test_user_id = "test_user_id_12345"
        print(f"  测试用户ID: {test_user_id}")
        print(f"  测试月份: {month}")
        
        record = storage.get_record_by_user_month(test_user_id, month)
        if record:
            print(f"  ✅ 查询成功，找到记录")
        else:
            print(f"  ℹ️  查询成功，未找到记录（这是正常的）")
    except Exception as e:
        print(f"  ❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. 测试创建记录
    print("\n[步骤 4] 测试创建记录")
    try:
        test_metrics = {
            "message_count": 1,
            "char_count": 10,
            "reply_received": 0,
            "mention_received": 0,
            "topic_initiated": 1
        }
        
        print(f"  正在创建测试记录...")
        storage.update_or_create_record(
            user_id=test_user_id,
            user_name="测试用户",
            metrics_delta=test_metrics
        )
        print(f"  ✅ 创建/更新成功")
    except Exception as e:
        print(f"  ❌ 创建/更新失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "="*60)
    print("✅ 所有诊断测试通过！")
    print("="*60)
    print("\n💡 建议：")
    print("1. 如果上述测试都通过，请检查飞书应用的事件订阅配置")
    print("2. 确认应用已订阅 'im.message.receive_v1' 事件")
    print("3. 检查应用权限是否包含：")
    print("   - 获取与发送单聊、群组消息")
    print("   - 读取用户发送的消息")
    print("   - 获取群组信息")
    print("   - 以应用身份读写多维表格")

if __name__ == "__main__":
    test_bitable_connection()
