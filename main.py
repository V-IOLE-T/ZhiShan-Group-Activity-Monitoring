import schedule
import time
from datetime import datetime
from auth import FeishuAuth
from collector import MessageCollector
from calculator import MetricsCalculator
from storage import BitableStorage

def job():
    print(f"\n{'='*50}")
    print(f"开始执行任务: {datetime.now()}")
    
    try:
        auth = FeishuAuth()
        auth.get_tenant_access_token()
        print("✅ 认证成功")
        
        collector = MessageCollector(auth)
        messages = collector.get_messages(hours=1)
        print(f"✅ 采集到 {len(messages)} 条消息")
        
        if not messages:
            print("⚠️  无新消息,跳过计算")
            return
        
        # 获取涉及的用户昵称
        user_ids = set()
        for msg in messages:
            sender_id_obj = msg.get('sender', {}).get('id', {})
            if isinstance(sender_id_obj, dict):
                user_ids.add(sender_id_obj.get('open_id'))
            elif isinstance(sender_id_obj, str):
                user_ids.add(sender_id_obj)
        
        user_names = collector.get_user_names(list(user_ids))
        print(f"✅ 已解析 {len(user_names)} 位用户昵称")
        
        calculator = MetricsCalculator(messages, user_names=user_names)
        metrics = calculator.calculate()
        print(f"✅ 计算完成,共 {len(metrics)} 位用户")
        
        sorted_users = sorted(
            metrics.items(), 
            key=lambda x: x[1]['score'], 
            reverse=True
        )[:10]
        
        print("\n🏆 活跃度 Top10:")
        for rank, (user_id, data) in enumerate(sorted_users, 1):
            print(f"{rank}. {data['user_name'][:10]} - {data['score']}分 "
                  f"(发言{data['message_count']}次)")
        
        storage = BitableStorage(auth)
        storage.save_metrics(metrics)
        print("✅ 数据已保存到多维表格")
        
    except Exception as e:
        print(f"❌ 任务执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 飞书群聊活跃度监测系统启动")
    
    job()
    
    schedule.every().hour.at(":00").do(job)
    
    print("⏰ 定时任务已设置: 每小时整点执行")
    
    while True:
        schedule.run_pending()
        time.sleep(60)
