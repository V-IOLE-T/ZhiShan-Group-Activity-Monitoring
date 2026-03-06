"""
月度归档器
每月 1 号自动将上月数据归档到历史表，并清空当月统计表
"""
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from auth import FeishuAuth

# 加载环境变量
env_path = Path(__file__).parent / "config" / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()


class MonthlyArchiver:
    """月度数据归档器"""
    
    def __init__(self, auth):
        self.auth = auth
        self.app_token = os.getenv("BITABLE_APP_TOKEN")
        self.current_table_id = os.getenv("BITABLE_TABLE_ID")
        self.archive_table_id = os.getenv("ARCHIVE_STATS_TABLE_ID")
        
        if not self.archive_table_id:
            print("⚠️  未配置 ARCHIVE_STATS_TABLE_ID，归档功能禁用")
    
    def should_archive_today(self):
        """判断今天是否需要执行归档"""
        now = datetime.now()
        # 每月 1 号凌晨 2:00-3:00 之间执行
        return now.day == 1 and 2 <= now.hour < 3
    
    def get_last_month_period(self):
        """获取上月的统计周期字符串"""
        # 获取上个月的年月
        today = datetime.now()
        first_day_this_month = today.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        return last_day_last_month.strftime("%Y-%m")
    
    def get_all_records(self):
        """获取当月表的所有记录"""
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.current_table_id}/records/search"
        
        all_records = []
        page_token = None
        
        print("📊 正在获取当月统计表的所有记录...")
        
        while True:
            params = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            
            try:
                response = requests.post(
                    url, 
                    headers=self.auth.get_headers(), 
                    params=params,
                    json={},
                    timeout=30
                )
                data = response.json()
                
                if data.get("code") != 0:
                    print(f"❌ 获取记录失败: {data.get('msg')}")
                    return None
                
                items = data.get("data", {}).get("items", [])
                all_records.extend(items)
                
                has_more = data.get("data", {}).get("has_more", False)
                if not has_more:
                    break
                
                page_token = data.get("data", {}).get("page_token")
                
            except Exception as e:
                print(f"❌ 获取记录异常: {e}")
                return None
        
        print(f"✅ 共获取 {len(all_records)} 条记录")
        return all_records
    
    def save_to_archive(self, record_fields):
        """保存记录到归档表"""
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.archive_table_id}/records"
        
        # 添加归档时间
        archive_fields = {
            **record_fields,
            "归档时间": int(datetime.now().timestamp() * 1000)
        }
        
        try:
            response = requests.post(
                url,
                headers=self.auth.get_headers(),
                json={"fields": archive_fields},
                timeout=10
            )
            result = response.json()
            
            if result.get("code") == 0:
                return True
            else:
                print(f"  ❌ 归档失败: {result.get('msg')}")
                return False
        except Exception as e:
            print(f"  ❌ 归档异常: {e}")
            return False
    
    def delete_record(self, record_id):
        """删除当月表中的记录"""
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.current_table_id}/records/{record_id}"
        
        try:
            response = requests.delete(
                url,
                headers=self.auth.get_headers(),
                timeout=10
            )
            result = response.json()
            
            if result.get("code") == 0:
                return True
            else:
                print(f"  ❌ 删除失败: {result.get('msg')}")
                return False
        except Exception as e:
            print(f"  ❌ 删除异常: {e}")
            return False
    
    def archive_and_clear(self):
        """执行归档并清空当月表"""
        if not self.archive_table_id:
            print("⚠️  归档表未配置，跳过归档")
            return False
        
        print(f"\n{'='*60}")
        print(f"📦 开始执行月度归档")
        print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"上月周期: {self.get_last_month_period()}")
        print(f"{'='*60}\n")
        
        # 1. 获取所有记录
        records = self.get_all_records()
        if records is None:
            print("❌ 归档失败: 无法获取记录")
            return False
        
        if len(records) == 0:
            print("💡 当月表为空，无需归档")
            return True
        
        # 2. 归档到历史表
        print(f"\n📥 正在归档 {len(records)} 条记录到历史表...")
        archived_count = 0
        failed_records = []
        
        for i, record in enumerate(records, 1):
            record_id = record.get("record_id")
            fields = record.get("fields", {})
            user_name = fields.get("用户名称", "未知")
            
            print(f"  [{i}/{len(records)}] 归档: {user_name}")
            
            if self.save_to_archive(fields):
                archived_count += 1
            else:
                failed_records.append(record_id)
        
        print(f"\n✅ 归档完成: {archived_count}/{len(records)} 条")
        
        if failed_records:
            print(f"⚠️  {len(failed_records)} 条记录归档失败，保留在当月表")
            return False
        
        # 3. 清空当月表
        print(f"\n🗑️  正在清空当月统计表...")
        deleted_count = 0
        
        for i, record in enumerate(records, 1):
            record_id = record.get("record_id")
            fields = record.get("fields", {})
            user_name = fields.get("用户名称", "未知")
            
            print(f"  [{i}/{len(records)}] 删除: {user_name}")
            
            if self.delete_record(record_id):
                deleted_count += 1
        
        print(f"\n✅ 清空完成: {deleted_count}/{len(records)} 条")
        
        print(f"\n{'='*60}")
        print(f"✅ 月度归档完成!")
        print(f"   归档: {archived_count} 条")
        print(f"   删除: {deleted_count} 条")
        print(f"{'='*60}\n")
        
        return True


def main():
    """主函数 - 用于手动测试"""
    print("🧪 月度归档测试模式\n")
    
    auth = FeishuAuth()
    archiver = MonthlyArchiver(auth)
    
    if not archiver.archive_table_id:
        print("❌ 请先在 config/.env 中配置 ARCHIVE_STATS_TABLE_ID")
        return
    
    # 询问用户是否执行
    print("⚠️  此操作将:")
    print("  1. 将当月表的所有记录复制到归档表")
    print("  2. 清空当月统计表")
    print()
    confirm = input("确认执行归档? (yes/no): ").strip().lower()
    
    if confirm == "yes":
        archiver.archive_and_clear()
    else:
        print("❌ 已取消")


if __name__ == "__main__":
    main()
