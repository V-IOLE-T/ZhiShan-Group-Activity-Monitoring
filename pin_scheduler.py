"""
Pin 周报后台调度器
集成到主进程中，使用 schedule 库定时执行
"""
import threading
import time
import schedule
from datetime import datetime
from pin_weekly_report import main as run_weekly_report


class PinReportScheduler:
    """Pin 周报后台调度器"""
    
    def __init__(self):
        self.running = False
        self.thread = None
    
    def start(self):
        """启动后台调度线程"""
        if self.running:
            print("⚠️  Pin 周报调度器已在运行")
            return
        
        self.running = True
        
        # 配置定时任务: 每周一早上 9:00
        schedule.every().monday.at("09:00").do(self._run_report_job)
        
        # 启动后台线程
        self.thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self.thread.start()
        
        print("✅ Pin 周报调度器已启动 (每周一 09:00)")
        print(f"   下次执行: {self._get_next_run_time()}")
    
    def stop(self):
        """停止后台调度线程"""
        self.running = False
        schedule.clear()
        print("🛑 Pin 周报调度器已停止")
    
    def _schedule_loop(self):
        """后台调度循环"""
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    def _run_report_job(self):
        """执行周报任务"""
        try:
            print(f"\n{'='*60}")
            print(f"🔔 定时任务触发: Pin 周报")
            print(f"   执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")
            
            run_weekly_report()
            
            print(f"\n{'='*60}")
            print(f"✅ Pin 周报执行完成")
            print(f"   下次执行: {self._get_next_run_time()}")
            print(f"{'='*60}\n")
        except Exception as e:
            print(f"❌ Pin 周报执行失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_next_run_time(self):
        """获取下次执行时间"""
        jobs = schedule.get_jobs()
        if jobs:
            next_run = jobs[0].next_run
            if next_run:
                return next_run.strftime('%Y-%m-%d %H:%M:%S')
        return "未安排"
    
    def run_now(self):
        """立即执行一次 (测试用)"""
        print("\n🧪 手动触发 Pin 周报...")
        self._run_report_job()


# 全局实例
_scheduler = None


def get_scheduler():
    """获取调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = PinReportScheduler()
    return _scheduler


def start_pin_scheduler():
    """启动 Pin 周报调度器"""
    scheduler = get_scheduler()
    scheduler.start()


def stop_pin_scheduler():
    """停止 Pin 周报调度器"""
    scheduler = get_scheduler()
    scheduler.stop()


def run_pin_report_now():
    """立即执行 Pin 周报 (测试用)"""
    scheduler = get_scheduler()
    scheduler.run_now()
