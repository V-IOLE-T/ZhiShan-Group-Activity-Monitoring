import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv
from config import ACTIVITY_WEIGHTS
from rate_limiter import with_rate_limit

load_dotenv()


class BitableStorage:
    def __init__(self, auth):
        self.auth = auth
        self.app_token = os.getenv("BITABLE_APP_TOKEN")
        self.table_id = os.getenv("BITABLE_TABLE_ID")

    @with_rate_limit
    def get_record_by_user_month(self, user_id, month):
        """根据用户ID和月份查找记录"""
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/search"
        payload = {
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {"field_name": "用户ID", "operator": "is", "value": [user_id]},
                    {"field_name": "统计周期", "operator": "is", "value": [month]},
                ],
            }
        }
        try:
            response = requests.post(url, headers=self.auth.get_headers(), json=payload, timeout=10)
            data = response.json()
            if data.get("code") != 0:
                print(f"  > [API] ⚠️  Bitable 搜索失败 (请检查是否已添加 '统计周期' 列): {data}")
                return None
            items = data.get("data", {}).get("items", [])
            if items:
                print(f"  > [API] ✅ 找到已存在的记录")
            else:
                print(f"  > [API] ℹ️  未找到记录，将创建新记录")
            return items[0] if items else None
        except requests.exceptions.Timeout:
            print(f"❌ 查找记录超时: 请求 Bitable API 超时")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ 查找记录请求出错: {e}")
            return None
        except Exception as e:
            print(f"❌ 查找记录出错: {e}")
            return None

    @with_rate_limit
    def update_or_create_record(self, user_id, user_name, metrics_delta):
        """按月实时更新或创建记录"""
        month = datetime.now().strftime("%Y-%m")
        record = self.get_record_by_user_month(user_id, month)

        fields = {
            "用户ID": user_id,
            "用户名称": user_name,
            "人员": [{"id": user_id}],  # 人员字段，关联飞书账号
            "统计周期": month,
            "更新时间": int(datetime.now().timestamp() * 1000),
        }

        if record:
            record_id = record["record_id"]
            old_fields = record["fields"]
            # 在本月旧数据基础上累加
            fields.update(
                {
                    "发言次数": int(old_fields.get("发言次数", 0))
                    + metrics_delta.get("message_count", 0),
                    "发言字数": int(old_fields.get("发言字数", 0))
                    + metrics_delta.get("char_count", 0),
                    "被回复数": int(old_fields.get("被回复数", 0))
                    + metrics_delta.get("reply_received", 0),
                    "单独被@次数": int(old_fields.get("单独被@次数", 0))
                    + metrics_delta.get("mention_received", 0),
                    "发起话题数": int(old_fields.get("发起话题数", 0))
                    + metrics_delta.get("topic_initiated", 0),
                    "点赞数": int(old_fields.get("点赞数", 0))
                    + metrics_delta.get("reaction_given", 0),
                    "被点赞数": int(old_fields.get("被点赞数", 0))
                    + metrics_delta.get("reaction_received", 0),
                }
            )
            # 重新计算分数（使用配置文件中的权重）
            score = (
                fields["发言次数"] * ACTIVITY_WEIGHTS["message_count"]
                + fields["发言字数"] * ACTIVITY_WEIGHTS["char_count"]
                + fields["被回复数"] * ACTIVITY_WEIGHTS["reply_received"]
                + fields["单独被@次数"] * ACTIVITY_WEIGHTS["mention_received"]
                + fields["发起话题数"] * ACTIVITY_WEIGHTS["topic_initiated"]
                + fields["点赞数"] * ACTIVITY_WEIGHTS["reaction_given"]
                + fields["被点赞数"] * ACTIVITY_WEIGHTS["reaction_received"]
            )
            fields["活跃度分数"] = round(score, 2)

            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}"
            print(f"  > [API] 正在更新记录 {record_id}...")
            try:
                response = requests.put(
                    url, headers=self.auth.get_headers(), json={"fields": fields}, timeout=10
                )
                result = response.json()
                if result.get("code") == 0:
                    print(f"  > [API] ✅ 更新成功")
                else:
                    print(f"  > [API] ❌ 更新失败: {result}")
                    print(f"  > [DEBUG] URL: {url}")
                    print(f"  > [DEBUG] Fields: {fields}")
                    raise Exception(f"Bitable API 返回错误: {result}")
            except requests.exceptions.Timeout:
                print(f"  > [API] ❌ 更新超时")
                raise
            except requests.exceptions.RequestException as e:
                print(f"  > [API] ❌ 请求异常: {e}")
                raise
        else:
            # 本月尚无记录，创建新行
            fields.update(
                {
                    "发言次数": metrics_delta.get("message_count", 0),
                    "发言字数": metrics_delta.get("char_count", 0),
                    "被回复数": metrics_delta.get("reply_received", 0),
                    "单独被@次数": metrics_delta.get("mention_received", 0),
                    "发起话题数": metrics_delta.get("topic_initiated", 0),
                    "点赞数": metrics_delta.get("reaction_given", 0),
                    "被点赞数": metrics_delta.get("reaction_received", 0),
                }
            )
            score = (
                fields["发言次数"] * ACTIVITY_WEIGHTS["message_count"]
                + fields["发言字数"] * ACTIVITY_WEIGHTS["char_count"]
                + fields["被回复数"] * ACTIVITY_WEIGHTS["reply_received"]
                + fields["单独被@次数"] * ACTIVITY_WEIGHTS["mention_received"]
                + fields["发起话题数"] * ACTIVITY_WEIGHTS["topic_initiated"]
                + fields["点赞数"] * ACTIVITY_WEIGHTS["reaction_given"]
                + fields["被点赞数"] * ACTIVITY_WEIGHTS["reaction_received"]
            )
            fields["活跃度分数"] = round(score, 2)

            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"
            print(f"  > [API] 正在创建新记录...")
            try:
                response = requests.post(
                    url, headers=self.auth.get_headers(), json={"fields": fields}, timeout=10
                )
                result = response.json()
                if result.get("code") == 0:
                    print(f"  > [API] ✅ 创建成功")
                else:
                    print(f"  > [API] ❌ 创建失败: {result}")
                    print(f"  > [DEBUG] URL: {url}")
                    print(f"  > [DEBUG] Fields: {fields}")
                    raise Exception(f"Bitable API 返回错误: {result}")
            except requests.exceptions.Timeout:
                print(f"  > [API] ❌ 创建超时")
                raise
            except requests.exceptions.RequestException as e:
                print(f"  > [API] ❌ 请求异常: {e}")
                raise

    @with_rate_limit
    def archive_pin_message(self, pin_info):
        """
        归档Pin消息到专用表

        Args:
            pin_info: Pin消息信息字典
        """
        pin_table_id = os.getenv("PIN_TABLE_ID")
        if not pin_table_id:
            print("[Pin归档] ⚠️ 未配置PIN_TABLE_ID，跳过归档")
            return False

        # 构建Bitable字段
        fields = {
            "Pin消息ID": pin_info.get("message_id"),
            "消息内容": pin_info.get("content", ""),
            "消息类型": pin_info.get("message_type", "text"),
            "发送者ID": pin_info.get("sender_id"),
            "发送者姓名": pin_info.get("sender_name"),
            "Pin操作人ID": pin_info.get("operator_id"),
            "Pin操作人姓名": pin_info.get("operator_name"),
            "Pin时间": pin_info.get("pin_time"),  # 文本格式: "2026-01-15 18:20:30"
            "消息发送时间": pin_info.get("create_time"),  # 文本格式
            "消息链接": {  # URL字段必须是对象格式
                "link": f"https://applink.feishu.cn/client/chat/open?openId={os.getenv('CHAT_ID')}",
                "text": "查看消息",
            },
            "归档时间": pin_info.get("archive_time"),  # 文本格式
        }

        # 添加附件(如果有)
        file_tokens = pin_info.get("file_tokens", [])
        if file_tokens:
            fields["附件信息"] = file_tokens

        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{pin_table_id}/records"

        try:
            response = requests.post(
                url, headers=self.auth.get_headers(), json={"fields": fields}, timeout=10
            )
            result = response.json()
            if result.get("code") == 0:
                print(f"[Pin归档] ✅ Pin消息已归档到Bitable")
                return True
            else:
                print(f"[Pin归档] ❌ 归档失败: {result}")
                return False
        except Exception as e:
            print(f"[Pin归档] ❌ 归档异常: {e}")
            return False

    @with_rate_limit
    def delete_pin_message(self, message_id):
        """
        从Pin归档表中删除记录

        Args:
            message_id: Pin消息ID
        """
        pin_table_id = os.getenv("PIN_TABLE_ID")
        if not pin_table_id:
            return False

        # 先查找记录ID
        search_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{pin_table_id}/records/search"
        search_payload = {
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {"field_name": "Pin消息ID", "operator": "is", "value": [message_id]}
                ],
            }
        }

        try:
            response = requests.post(
                search_url, headers=self.auth.get_headers(), json=search_payload, timeout=10
            )
            data = response.json()

            if data.get("code") == 0:
                items = data.get("data", {}).get("items", [])
                if not items:
                    print(f"[Pin删除] ⚠️ 未找到Pin记录: {message_id}")
                    return False

                record_id = items[0]["record_id"]

                # 删除记录
                delete_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{pin_table_id}/records/{record_id}"
                del_response = requests.delete(
                    delete_url, headers=self.auth.get_headers(), timeout=10
                )
                del_result = del_response.json()

                if del_result.get("code") == 0:
                    print(f"[Pin删除] ✅ 已删除Pin归档记录")
                    return True
                else:
                    print(f"[Pin删除] ❌ 删除失败: {del_result}")
                    return False
        except Exception as e:
            print(f"[Pin删除] ❌ 删除异常: {e}")
            return False

    @with_rate_limit
    def increment_pin_count(self, user_id, user_name):
        """
        增加用户被Pin次数统计

        Args:
            user_id: 用户ID
            user_name: 用户名称
        """
        month = datetime.now().strftime("%Y-%m")
        record = self.get_record_by_user_month(user_id, month)

        if record:
            record_id = record["record_id"]
            old_fields = record["fields"]
            current_count = int(old_fields.get("被Pin次数", 0))
            new_count = current_count + 1

            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}"
            fields = {"被Pin次数": new_count}

            try:
                response = requests.put(
                    url, headers=self.auth.get_headers(), json={"fields": fields}, timeout=10
                )
                result = response.json()
                if result.get("code") == 0:
                    print(f"[Pin统计] ✅ {user_name} 被Pin次数: {current_count} -> {new_count}")
                else:
                    print(f"[Pin统计] ❌ 更新被Pin次数失败: {result}")
            except Exception as e:
                print(f"[Pin统计] ❌ 更新异常: {e}")
        else:
            # 如果本月还没有活跃度记录，创建一条只有被Pin次数的记录
            fields = {
                "用户ID": user_id,
                "用户名称": user_name,
                "人员": [{"id": user_id}],
                "统计周期": month,
                "被Pin次数": 1,
                "发言次数": 0,
                "发言字数": 0,
                "被回复数": 0,
                "单独被@次数": 0,
                "发起话题数": 0,
                "点赞数": 0,
                "被点赞数": 0,
                "活跃度分数": 0,
                "更新时间": int(datetime.now().timestamp() * 1000),
            }

            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"
            try:
                response = requests.post(
                    url, headers=self.auth.get_headers(), json={"fields": fields}, timeout=10
                )
                result = response.json()
                if result.get("code") == 0:
                    print(f"[Pin统计] ✅ 为 {user_name} 创建新记录，被Pin次数: 1")
                else:
                    print(f"[Pin统计] ❌ 创建记录失败: {result}")
            except Exception as e:
                print(f"[Pin统计] ❌ 创建异常: {e}")

    @with_rate_limit
    def decrement_pin_count(self, user_id, user_name):
        """
        减少用户被Pin次数统计

        Args:
            user_id: 用户ID
            user_name: 用户名称
        """
        month = datetime.now().strftime("%Y-%m")
        record = self.get_record_by_user_month(user_id, month)

        if record:
            record_id = record["record_id"]
            old_fields = record["fields"]
            current_count = int(old_fields.get("被Pin次数", 0))
            new_count = max(0, current_count - 1)  # 确保不会小于0

            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}"
            fields = {"被Pin次数": new_count}

            try:
                response = requests.put(
                    url, headers=self.auth.get_headers(), json={"fields": fields}, timeout=10
                )
                result = response.json()
                if result.get("code") == 0:
                    print(f"[Pin统计] ✅ {user_name} 被Pin次数: {current_count} -> {new_count}")
                else:
                    print(f"[Pin统计] ❌ 更新被Pin次数失败: {result}")
            except Exception as e:
                print(f"[Pin统计] ❌ 更新异常: {e}")


class MessageArchiveStorage:
    def __init__(self, auth):
        self.auth = auth
        self.app_token = os.getenv("BITABLE_APP_TOKEN")
        self.archive_table_id = os.getenv("ARCHIVE_TABLE_ID")
        self.summary_table_id = os.getenv("SUMMARY_TABLE_ID")

    @with_rate_limit
    def save_message(self, fields):
        """保存单条消息到归档表"""
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.archive_table_id}/records"
        try:
            response = requests.post(
                url, headers=self.auth.get_headers(), json={"fields": fields}, timeout=10
            )
            result = response.json()
            if result.get("code") == 0:
                print(f"  > [归档] ✅ 消息模型已存入 Bitable")
                return True
            else:
                print(f"  > [归档] ❌ 存储失败: {result}")
                return False
        except Exception as e:
            print(f"  > [归档] ❌ 归档出错: {e}")
            return False

    @with_rate_limit
    def get_topic_by_id(self, topic_id):
        """根据话题ID查找话题汇总记录"""
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.summary_table_id}/records/search"
        payload = {
            "filter": {
                "conjunction": "and",
                "conditions": [{"field_name": "话题ID", "operator": "is", "value": [topic_id]}],
            }
        }
        try:
            response = requests.post(url, headers=self.auth.get_headers(), json=payload, timeout=10)
            data = response.json()
            if data.get("code") == 0:
                items = data.get("data", {}).get("items", [])
                return items[0] if items else None
        except Exception as e:
            print(f"  > [汇总] 🔍 查找话题出错: {e}")
        return None

    @with_rate_limit
    def update_or_create_topic(self, topic_id, fields, is_new=False):
        """创建或更新话题汇总记录"""
        if is_new:
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.summary_table_id}/records"
            resp = requests.post(
                url, headers=self.auth.get_headers(), json={"fields": fields}, timeout=10
            )
        else:
            # 先找到 record_id
            record = self.get_topic_by_id(topic_id)
            if not record:
                return False
            record_id = record["record_id"]
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.summary_table_id}/records/{record_id}"
            resp = requests.put(
                url, headers=self.auth.get_headers(), json={"fields": fields}, timeout=10
            )

        result = resp.json()
        return result.get("code") == 0

    def download_message_resource(self, message_id, file_key, resource_type):
        """从飞书消息中下载资源（图片或文件）"""
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}"
        params = {"type": resource_type}
        try:
            response = requests.get(url, headers=self.auth.get_headers(), params=params, timeout=30)
            if response.status_code == 200:
                return response.content
            else:
                print(f"  > [附件] ❌ 下载资源失败: {response.status_code}")
                print(f"  > [附件] 响应: {response.text[:200]}")
                return None
        except Exception as e:
            print(f"  > [附件] ❌ 下载资源出错: {e}")
            return None

    def upload_file_to_drive(self, file_content, file_name):
        """将文件作为素材上传到多维表格，获取可用于 Bitable 的 file_token
        使用素材上传 API: /drive/v1/medias/upload_all
        """
        url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"

        # 准备表单数据 - 上传到多维表格作为素材
        form_data = {
            "file_name": file_name,
            "parent_type": "bitable_file",  # 上传至多维表格素材
            "parent_node": self.app_token,  # 目标多维表格的 app_token
            "size": str(len(file_content)),
        }

        files = {"file": (file_name, file_content)}

        # 创建不包含 Content-Type 的 headers
        upload_headers = {"Authorization": self.auth.get_headers()["Authorization"]}

        try:
            response = requests.post(
                url, headers=upload_headers, data=form_data, files=files, timeout=60
            )

            if response.status_code != 200:
                print(f"  > [附件] ❌ 上传素材 HTTP 错误: {response.status_code}")
                print(f"  > [附件] 响应内容: {response.text[:200]}")
                return None

            try:
                result = response.json()
            except Exception as e:
                print(f"  > [附件] ❌ 解析响应 JSON 失败: {e}")
                print(f"  > [附件] 原始响应: {response.text[:200]}")
                return None

            if result.get("code") == 0:
                data_obj = result.get("data", {})
                file_token = data_obj.get("file_token")
                if file_token:
                    print(f"  > [附件] ✅ 素材已上传到多维表格: {file_token}")
                    # 返回 Bitable 附件字段需要的格式
                    return {
                        "file_token": file_token,
                        "name": file_name,
                        "size": len(file_content),
                        "type": "file",
                    }
                else:
                    print(f"  > [附件] ❌ 响应中未找到 file_token: {result}")
                    return None
            else:
                print(f"  > [附件] ❌ 上传素材失败: {result}")
                return None
        except Exception as e:
            print(f"  > [附件] ❌ 上传素材出错: {e}")
            return None
