"""
检查多维表格的字段配置
"""
import os
import requests
from dotenv import load_dotenv
from auth import FeishuAuth

load_dotenv()

def check_table_fields():
    print("="*60)
    print("🔍 检查多维表格字段配置")
    print("="*60)
    
    # 初始化认证
    auth = FeishuAuth()
    auth.get_tenant_access_token()
    
    app_token = os.getenv('BITABLE_APP_TOKEN')
    table_id = os.getenv('BITABLE_TABLE_ID')
    
    # 获取表格字段列表
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
    
    try:
        response = requests.get(
            url,
            headers=auth.get_headers(),
            timeout=10
        )
        result = response.json()
        
        if result.get('code') != 0:
            print(f"❌ 获取字段列表失败: {result}")
            return
        
        fields = result.get('data', {}).get('items', [])
        
        print(f"\n✅ 成功获取字段列表，共 {len(fields)} 个字段\n")
        print("当前表格中的字段：")
        print("-" * 60)
        
        for idx, field in enumerate(fields, 1):
            field_name = field.get('field_name', '')
            field_type = field.get('type', '')
            print(f"{idx}. 字段名: {field_name}")
            print(f"   字段类型: {field_type}")
            print()
        
        # 检查必需字段
        print("="*60)
        print("检查必需字段：")
        print("="*60)
        
        required_fields = [
            "用户ID",
            "用户名称",
            "人员",
            "统计周期",
            "更新时间",
            "发言次数",
            "发言字数",
            "被回复数",
            "单独被@次数",
            "发起话题数",
            "点赞数",
            "被点赞数",
            "活跃度分数"
        ]
        
        existing_field_names = [f.get('field_name', '') for f in fields]
        
        missing_fields = []
        for required in required_fields:
            if required in existing_field_names:
                print(f"✅ {required}")
            else:
                print(f"❌ {required} - 缺失！")
                missing_fields.append(required)
        
        if missing_fields:
            print(f"\n⚠️  缺少 {len(missing_fields)} 个必需字段！")
            print("\n请在飞书多维表格中添加以下字段：")
            for field in missing_fields:
                print(f"  - {field}")
            
            print("\n建议的字段类型：")
            print("  - 用户ID: 文本")
            print("  - 用户名称: 文本")
            print("  - 人员: 人员")
            print("  - 统计周期: 文本")
            print("  - 更新时间: 数字")
            print("  - 发言次数: 数字")
            print("  - 发言字数: 数字")
            print("  - 被回复数: 数字")
            print("  - 单独被@次数: 数字")
            print("  - 发起话题数: 数字")
            print("  - 点赞数: 数字")
            print("  - 被点赞数: 数字")
            print("  - 活跃度分数: 数字")
        else:
            print("\n✅ 所有必需字段都已配置！")
            
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_table_fields()
