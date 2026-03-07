"""
月度归档器

按统计周期归档上月数据到历史表，并在确认归档完成后清理当前表。
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import requests
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

    STATE_FILE = Path(__file__).parent / ".last_monthly_archive.txt"
    PAGE_SIZE = 500
    COMPENSATION_WINDOW_DAYS = 3

    def __init__(self, auth):
        self.auth = auth
        self.app_token = os.getenv("BITABLE_APP_TOKEN")
        self.current_table_id = os.getenv("BITABLE_TABLE_ID")
        self.archive_table_id = os.getenv("ARCHIVE_STATS_TABLE_ID")

        if not self.archive_table_id:
            print("⚠️  未配置 ARCHIVE_STATS_TABLE_ID，归档功能禁用")

    def get_last_month_period(self, today: Optional[datetime] = None) -> str:
        """获取上月的统计周期字符串。"""
        today = today or datetime.now()
        first_day_this_month = today.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        return last_day_last_month.strftime("%Y-%m")

    def is_within_compensation_window(self, now: Optional[datetime] = None) -> bool:
        """是否处于月初补偿窗口内。"""
        now = now or datetime.now()
        return 1 <= now.day <= self.COMPENSATION_WINDOW_DAYS

    def get_last_completed_period(self) -> Optional[str]:
        """读取最近一次完整成功的归档周期。"""
        if not self.STATE_FILE.exists():
            return None

        try:
            period = self.STATE_FILE.read_text(encoding="utf-8").strip()
            return period or None
        except Exception as e:
            print(f"⚠️  读取月度归档状态失败: {e}")
            return None

    def mark_period_completed(self, period: str) -> bool:
        """记录某个周期已完整归档。"""
        try:
            self.STATE_FILE.write_text(period, encoding="utf-8")
            return True
        except Exception as e:
            print(f"⚠️  写入月度归档状态失败: {e}")
            return False

    def should_run_startup_compensation(self, now: Optional[datetime] = None) -> bool:
        """启动时是否需要执行月初补偿检查。"""
        now = now or datetime.now()
        if not self.is_within_compensation_window(now):
            return False

        target_period = self.get_last_month_period(now)
        return self.get_last_completed_period() != target_period

    def should_run_scheduled_archive(self, now: Optional[datetime] = None) -> bool:
        """定时任务是否需要执行归档。"""
        now = now or datetime.now()
        if now.day == 1:
            return True

        if not self.is_within_compensation_window(now):
            return False

        target_period = self.get_last_month_period(now)
        return self.get_last_completed_period() != target_period

    def _search_records(self, table_id: str, payload: Optional[dict] = None) -> Optional[List[dict]]:
        """搜索表格记录，支持自动翻页。"""
        url = (
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}"
            f"/tables/{table_id}/records/search"
        )

        all_records: List[dict] = []
        page_token = None

        while True:
            params = {"page_size": self.PAGE_SIZE}
            if page_token:
                params["page_token"] = page_token

            try:
                response = requests.post(
                    url,
                    headers=self.auth.get_headers(),
                    params=params,
                    json=payload or {},
                    timeout=30,
                )
                data = response.json()
            except Exception as e:
                print(f"❌ 获取记录异常: {e}")
                return None

            if data.get("code") != 0:
                print(f"❌ 获取记录失败: {data.get('msg')}")
                return None

            items = data.get("data", {}).get("items", [])
            all_records.extend(items)

            has_more = data.get("data", {}).get("has_more", False)
            if not has_more:
                break

            page_token = data.get("data", {}).get("page_token")

        return all_records

    def get_records_for_period(self, period: str) -> Optional[List[dict]]:
        """获取指定统计周期的当前表记录。"""
        print(f"📊 正在获取统计周期 {period} 的记录...")
        payload = {
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {"field_name": "统计周期", "operator": "is", "value": [period]},
                ],
            }
        }
        records = self._search_records(self.current_table_id, payload)
        if records is not None:
            print(f"✅ 周期 {period} 共获取 {len(records)} 条记录")
        return records

    def archive_record_exists(self, user_id: str, period: str) -> Optional[bool]:
        """检查历史表中是否已存在同一用户同一周期的归档记录。"""
        payload = {
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {"field_name": "用户ID", "operator": "is", "value": [user_id]},
                    {"field_name": "统计周期", "operator": "is", "value": [period]},
                ],
            }
        }
        records = self._search_records(self.archive_table_id, payload)
        if records is None:
            return None
        return bool(records)

    def save_to_archive(self, record_fields):
        """保存记录到归档表"""
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.archive_table_id}/records"

        # 添加归档时间
        archive_fields = {
            **record_fields,
            "归档时间": int(datetime.now().timestamp() * 1000),
        }

        try:
            response = requests.post(
                url,
                headers=self.auth.get_headers(),
                json={"fields": archive_fields},
                timeout=10,
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
                timeout=10,
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
    
    def archive_and_clear(self, target_period: Optional[str] = None) -> bool:
        """按统计周期执行归档并清理当前表中的目标周期记录。"""
        if not self.archive_table_id:
            print("⚠️  归档表未配置，跳过归档")
            return False
        if not self.app_token or not self.current_table_id:
            print("⚠️  当前活跃度表配置不完整，跳过归档")
            return False

        target_period = target_period or self.get_last_month_period()
        last_completed_period = self.get_last_completed_period()

        print(f"\n{'='*60}")
        print(f"📦 开始执行月度归档")
        print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"目标周期: {target_period}")
        print(f"{'='*60}\n")

        records = self.get_records_for_period(target_period)
        if records is None:
            print("❌ 归档失败: 无法获取记录")
            return False

        if not records:
            if last_completed_period == target_period:
                print(f"💡 周期 {target_period} 已完成归档，无需重复执行")
            else:
                print(f"💡 周期 {target_period} 无待归档记录")
            return True

        if last_completed_period == target_period:
            print(
                f"⚠️  周期 {target_period} 已标记完成，但当前表仍有 {len(records)} 条记录，"
                "将继续执行补偿归档"
            )

        print(f"\n📥 正在处理 {len(records)} 条记录...")
        archived_count = 0
        skipped_existing = 0
        deleted_count = 0
        failed_records = []
        deletable_records = []

        for i, record in enumerate(records, 1):
            record_id = record.get("record_id")
            fields = record.get("fields", {})
            user_name = fields.get("用户名称", "未知")
            user_id = fields.get("用户ID")
            record_period = fields.get("统计周期")

            if not user_id or not record_period:
                print(f"  [{i}/{len(records)}] ❌ 缺少用户ID或统计周期: {user_name}")
                failed_records.append(record_id or f"invalid:{i}")
                continue

            exists = self.archive_record_exists(user_id, record_period)
            if exists is None:
                print(f"  [{i}/{len(records)}] ❌ 无法确认历史表是否已存在: {user_name}")
                failed_records.append(record_id or f"lookup:{i}")
                continue

            if exists:
                skipped_existing += 1
                deletable_records.append(record)
                print(f"  [{i}/{len(records)}] 跳过写入（历史表已存在）: {user_name}")
                continue

            print(f"  [{i}/{len(records)}] 归档: {user_name}")
            if self.save_to_archive(fields):
                archived_count += 1
                deletable_records.append(record)
            else:
                failed_records.append(record_id or f"archive:{i}")

        if failed_records:
            print(
                f"\n❌ 月度归档未完成: target_period={target_period} scanned={len(records)} "
                f"archived={archived_count} skipped_existing={skipped_existing} "
                f"deleted={deleted_count} failed={len(failed_records)}"
            )
            print("⚠️  存在归档失败记录，本次不执行删除，等待下次补偿")
            return False

        print(f"\n🗑️  正在删除周期 {target_period} 的当前表记录...")
        for i, record in enumerate(deletable_records, 1):
            record_id = record.get("record_id")
            fields = record.get("fields", {})
            user_name = fields.get("用户名称", "未知")

            print(f"  [{i}/{len(deletable_records)}] 删除: {user_name}")
            if self.delete_record(record_id):
                deleted_count += 1
            else:
                failed_records.append(record_id or f"delete:{i}")

        if failed_records:
            print(
                f"\n❌ 月度归档未完成: target_period={target_period} scanned={len(records)} "
                f"archived={archived_count} skipped_existing={skipped_existing} "
                f"deleted={deleted_count} failed={len(failed_records)}"
            )
            print("⚠️  删除阶段存在失败记录，不写入完成状态，等待下次补偿")
            return False

        if not self.mark_period_completed(target_period):
            print(
                f"\n❌ 月度归档未完成: target_period={target_period} scanned={len(records)} "
                f"archived={archived_count} skipped_existing={skipped_existing} "
                f"deleted={deleted_count} failed=1"
            )
            print("⚠️  完成状态写入失败，不写入成功结论，等待下次补偿")
            return False

        print(f"\n{'='*60}")
        print(f"✅ 月度归档完成!")
        print(
            f"   target_period={target_period} scanned={len(records)} "
            f"archived={archived_count} skipped_existing={skipped_existing} "
            f"deleted={deleted_count} failed=0"
        )
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

    target_period = archiver.get_last_month_period()
    # 询问用户是否执行
    print("⚠️  此操作将:")
    print(f"  1. 将统计周期 {target_period} 的记录复制到历史归档表")
    print(f"  2. 删除当前表中统计周期 {target_period} 的记录")
    print()
    confirm = input("确认执行归档? (yes/no): ").strip().lower()

    if confirm == "yes":
        archiver.archive_and_clear(target_period=target_period)
    else:
        print("❌ 已取消")


if __name__ == "__main__":
    main()
