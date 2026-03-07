"""
每周 Pin 审计 & 月度归档后台调度器
集成到主进程中，使用 schedule 库定时执行
"""
import threading
import time
import os
import schedule
from datetime import datetime
from storage import BitableStorage, DocxStorage
from pin_daily_audit import DailyPinAuditor


class PinReportScheduler:
    """每周 Pin 审计 & 月度归档后台调度器"""
    
    def __init__(self, auth=None):
        self.running = False
        self.thread = None
        self.auth = auth
        self.archiver = None
        self.pin_auditor = None
        
        # 延迟导入初始化（避免循环导入）
        if auth:
            try:
                from monthly_archiver import MonthlyArchiver
                self.archiver = MonthlyArchiver(auth)
            except Exception as e:
                print(f"⚠️  月度归档器初始化失败: {e}")
            
            try:
                chat_id = os.getenv("CHAT_ID")
                storage = BitableStorage(auth)
                docx_storage = DocxStorage(auth)
                essence_doc_token = os.getenv("ESSENCE_DOC_TOKEN")
                self.pin_auditor = DailyPinAuditor(
                    auth, storage, chat_id, docx_storage=docx_storage, essence_doc_token=essence_doc_token
                )
            except Exception as e:
                print(f"⚠️  每周 Pin 审计器初始化失败: {e}")
    
    def start(self):
        """启动后台调度线程"""
        if self.running:
            print("⚠️  调度器已在运行")
            return
        
        self.running = True
        
        # 配置定时任务
        # 1. 每周一 09:00：处理上周新增 Pin（按 Pin 操作时间）
        if self.pin_auditor:
            schedule.every().monday.at("09:00").do(self._run_weekly_pin_job)
            print("✅ 每周 Pin 审计调度已启动 (每周一 09:00)")
        else:
            print("⚠️  每周 Pin 审计器不可用，跳过该调度任务")
        
        # 2. 月度归档: 每天凌晨 2:00 检查是否需要归档
        if self.archiver and self.archiver.archive_table_id:
            schedule.every().day.at("02:00").do(self._run_archive_job)
            print("✅ 月度归档调度器已启动 (每月 1 号 02:00，月初 3 天内补偿)")
            self._run_archive_startup_check()
        
        # 启动后台线程
        self.thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self.thread.start()
        
        print("✅ 调度器已启动")
        print(f"   下次执行: {self._get_next_run_time()}")
    
    def stop(self):
        """停止后台调度线程"""
        self.running = False
        schedule.clear()
        print("🛑 调度器已停止")
    
    def _schedule_loop(self):
        """后台调度循环"""
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    def _run_weekly_pin_job(self):
        """执行每周 Pin 审计任务"""
        try:
            print(f"\n{'='*60}")
            print(f"🔔 定时任务触发: 每周 Pin 审计")
            print(f"   执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")
            
            count = self.pin_auditor.run_for_last_week() if self.pin_auditor else 0
            
            print(f"\n{'='*60}")
            print(f"✅ 每周 Pin 审计执行完成: {count} 条")
            print(f"   下次执行: {self._get_next_run_time()}")
            print(f"{'='*60}\n")
        except Exception as e:
            print(f"❌ 每周 Pin 审计执行失败: {e}")
            import traceback
            traceback.print_exc()

    def _run_daily_pin_job(self):
        """兼容旧方法名：执行每周 Pin 审计任务"""
        self._run_weekly_pin_job()

    def _run_archive_startup_check(self):
        """启动时执行一次月度归档补偿检查。"""
        if not self.archiver:
            return
        if not self.archiver.should_run_startup_compensation():
            return
        try:
            print("\n🔎 启动时执行月度归档补偿检查...")
            self.archiver.archive_and_clear()
        except Exception as e:
            print(f"❌ 月度归档补偿检查失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _run_archive_job(self):
        """执行月度归档任务。"""
        if not self.archiver:
            return
        if not self.archiver.should_run_scheduled_archive():
            return

        try:
            print(f"\n{'='*60}")
            print(f"🔔 定时任务触发: 月度归档")
            print(f"   执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")
            
            self.archiver.archive_and_clear()
            
            print(f"\n{'='*60}")
            print(f"✅ 月度归档执行完成")
            print(f"{'='*60}\n")
        except Exception as e:
            print(f"❌ 月度归档执行失败: {e}")
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
        """立即执行一次每周 Pin 审计 (测试用)"""
        print("\n🧪 手动触发每周 Pin 审计...")
        self._run_weekly_pin_job()
    
    def run_archive_now(self):
        """立即执行一次月度归档 (测试用)"""
        if not self.archiver:
            print("❌ 归档器未初始化")
            return
        print("\n🧪 手动触发月度归档...")
        self.archiver.archive_and_clear()


# 全局实例
_scheduler = None


def get_scheduler(auth=None):
    """获取调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = PinReportScheduler(auth)
    return _scheduler


def start_pin_scheduler(auth=None):
    """启动每周 Pin 审计 & 月度归档调度器"""
    scheduler = get_scheduler(auth)
    scheduler.start()


def stop_pin_scheduler():
    """停止调度器"""
    scheduler = get_scheduler()
    scheduler.stop()


def run_pin_audit_now():
    """立即执行每周 Pin 审计 (测试用)"""
    scheduler = get_scheduler()
    scheduler.run_now()


def run_archive_now():
    """立即执行月度归档 (测试用)"""
    scheduler = get_scheduler()
    scheduler.run_archive_now()


def run_pin_report_now():
    """兼容旧方法名：立即执行每周 Pin 审计 (测试用)"""
    run_pin_audit_now()
