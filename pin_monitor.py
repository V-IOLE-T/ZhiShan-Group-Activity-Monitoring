import os
import json
import time
import requests
import threading
from collections import OrderedDict
from datetime import datetime
from dotenv import load_dotenv
from rate_limiter import with_rate_limit

load_dotenv()


class LRUCache:
    """简单的LRU缓存实现，防止内存泄漏"""
    def __init__(self, capacity=500):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key, default=None):
        if key not in self.cache:
            return default
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def __contains__(self, key):
        return key in self.cache

    def __len__(self):
        return len(self.cache)


class PinMonitor:
    """Pin消息监控类 - 定期轮询检测Pin消息变化"""
    
    def __init__(self, auth, storage, chat_id, interval=30):
        """
        初始化Pin监控器
        
        Args:
            auth: FeishuAuth实例
            storage: BitableStorage实例 (用于统计被Pin次数)
            chat_id: 要监控的群组ID
            interval: 轮询间隔(秒)，默认30秒
        """
        self.auth = auth
        self.storage = storage
        self.chat_id = chat_id
        self.interval = interval
        
        # 缓存当前Pin消息ID列表
        self.current_pin_ids = set()
        
        # 缓存Pin消息详情(避免重复获取)
        self.pin_details_cache = LRUCache(capacity=200)
        
        # 用户昵称缓存
        self.user_name_cache = LRUCache(capacity=500)
        
        # 是否为首次运行(避免首次启动时对所有现有Pin发送提醒)
        self.is_first_run = True
        
        # 运行状态
        self.running = False
        self.monitor_thread = None

    @with_rate_limit
    def get_pinned_messages(self):
        """
        获取群内所有Pin消息列表
        
        Returns:
            list: Pin消息列表，每个元素包含message_id和operator_id
        """
        url = "https://open.feishu.cn/open-apis/im/v1/pins"  # 修正: open-apis(有s)
        headers = {
            "Authorization": f"Bearer {self.auth.get_tenant_access_token()}",
            "Content-Type": "application/json"
        }
        params = {
            "chat_id": self.chat_id  # 修正: 使用chat_id而不是container_id
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            # 打印响应状态
            if response.status_code != 200:
                print(f"[Pin监控] ❌ HTTP错误: {response.status_code}")
                print(f"[Pin监控] 响应内容: {response.text[:200]}")
                return []
            
            # 尝试解析JSON
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                print(f"[Pin监控] ❌ JSON解析失败: {e}")
                print(f"[Pin监控] 响应内容: {response.text[:200]}")
                return []
            
            if data.get("code") == 0:
                pins = data.get("data", {}).get("items", [])
                print(f"[Pin监控] 当前群内Pin消息数量: {len(pins)}")
                return pins
            else:
                print(f"[Pin监控] ❌ API返回错误: code={data.get('code')}, msg={data.get('msg')}")
                return []
        except requests.exceptions.Timeout:
            print(f"[Pin监控] ❌ 请求超时")
            return []
        except requests.exceptions.RequestException as e:
            print(f"[Pin监控] ❌ 请求异常: {e}")
            return []
        except Exception as e:
            print(f"[Pin监控] ❌ 未知异常: {e}")
            return []

    @with_rate_limit
    def get_message_details(self, message_id):
        """
        获取消息详细信息
        
        Args:
            message_id: 消息ID
            
        Returns:
            dict: 消息详情，包含发送者、内容、类型、附件等
        """
        # 检查缓存
        if message_id in self.pin_details_cache:
            return self.pin_details_cache.get(message_id)
        
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
        headers = {
            "Authorization": f"Bearer {self.auth.get_tenant_access_token()}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") == 0:
                message_data = data.get("data", {}).get("items", [{}])[0]
                msg_type = message_data.get("msg_type")
                content_str = message_data.get("body", {}).get("content", "")
                
                # 使用calculator的方法提取纯文本和图片keys
                from calculator import MetricsCalculator
                text_content, image_keys = MetricsCalculator.extract_text_from_content(content_str)
                
                # 解析content获取文件信息
                try:
                    content_obj = json.loads(content_str) if isinstance(content_str, str) else content_str
                except:
                    content_obj = {}
                
                details = {
                    "sender_id": message_data.get("sender", {}).get("id"),
                    "message_type": msg_type,
                    "content": text_content,  # 纯文本内容
                    "create_time": message_data.get("create_time"),
                    "chat_id": message_data.get("chat_id"),
                    "image_keys": image_keys,  # 富文本中的图片keys
                    "file_key": content_obj.get("file_key"),  # 文件消息的file_key
                    "file_name": content_obj.get("file_name"),  # 文件名
                    "image_key": content_obj.get("image_key")  # 图片消息的image_key
                }
                
                # 存入缓存
                self.pin_details_cache.set(message_id, details)
                return details
            else:
                print(f"[Pin监控] ❌ 获取消息详情失败: {data.get('msg')}")
                return None
        except Exception as e:
            print(f"[Pin监控] ❌ 获取消息详情异常: {e}")
            return None

    def get_user_name(self, user_id):
        """获取用户昵称（带缓存）"""
        if not user_id:
            return user_id
            
        if user_id in self.user_name_cache:
            return self.user_name_cache.get(user_id)
        
        # 使用collector获取群备注
        try:
            from collector import MessageCollector
            collector = MessageCollector(self.auth)
            names = collector.get_user_names([user_id])
            if names:
                for uid, name in names.items():
                    self.user_name_cache.set(uid, name)
                return names.get(user_id, user_id)
        except Exception as e:
            print(f"[Pin监控] 获取用户名失败: {e}")
        
        return user_id

    def send_pin_notification(self, message_id, pin_info):
        """
        发送Pin消息提醒卡片到群聊
        
        Args:
            message_id: 被Pin的消息ID
            pin_info: Pin信息字典
        """
        sender_name = pin_info.get("sender_name", "未知用户")
        operator_name = pin_info.get("operator_name", "管理员")
        content = pin_info.get("content", "")  # 不截断,显示全部内容
        file_tokens = pin_info.get("file_tokens", [])
        
        # 构建左侧元素(人员信息)
        left_column_elements = [
            {
                "tag": "markdown",
                "content": f"**Pin操作人**\n{operator_name}"
            },
            {
                "tag": "markdown", 
                "content": f"**话题发起人**\n{sender_name}"
            }
        ]
        
        # 构建右侧元素(话题内容)
        right_column_elements = [
            {
                "tag": "markdown",
                "content": f"**话题内容**\n{content}"
            }
        ]
        # 不显示附件
        
        # 构建消息卡片 - 使用列布局
        card_content = {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "orange",
                "title": {
                    "tag": "plain_text",
                    "content": "🔥 新增加精话题"
                }
            },
            "elements": [
                {
                    "tag": "column_set",
                    "flex_mode": "none",
                    "background_style": "default",
                    "columns": [
                        {
                            "tag": "column",
                            "width": "weighted",
                            "weight": 1,
                            "vertical_align": "top",
                            "elements": left_column_elements
                        },
                        {
                            "tag": "column",
                            "width": "weighted", 
                            "weight": 2,
                            "vertical_align": "top",
                            "elements": right_column_elements
                        }
                    ]
                }
            ]
        }
        
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {self.auth.get_tenant_access_token()}",
            "Content-Type": "application/json"
        }
        params = {"receive_id_type": "chat_id"}
        body = {
            "receive_id": self.chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card_content)
        }
        
        try:
            response = requests.post(url, headers=headers, params=params, json=body, timeout=10)
            data = response.json()
            if data.get("code") == 0:
                print(f"[Pin监控] ✅ 发送提醒卡片成功")
            else:
                print(f"[Pin监控] ❌ 发送提醒卡片失败: {data.get('msg')}")
        except Exception as e:
            print(f"[Pin监控] ❌ 发送提醒卡片异常: {e}")

    def check_pin_changes(self):
        """检查Pin消息变化并处理"""
        pins = self.get_pinned_messages()
        
        # 提取当前Pin消息ID集合
        new_pin_ids = {pin.get("message_id") for pin in pins if pin.get("message_id")}
        
        if self.is_first_run:
            # 首次运行，只缓存不处理
            print(f"[Pin监控] 首次运行，缓存当前 {len(new_pin_ids)} 条Pin消息")
            self.current_pin_ids = new_pin_ids
            self.is_first_run = False
            return
        
        # 检测新增的Pin
        newly_pinned = new_pin_ids - self.current_pin_ids
        # 检测取消的Pin
        unpinned = self.current_pin_ids - new_pin_ids
        
        # 处理新增Pin
        for message_id in newly_pinned:
            self._handle_new_pin(message_id, pins)
        
        # 处理取消Pin
        for message_id in unpinned:
            self._handle_unpin(message_id)
        
        # 更新缓存
        self.current_pin_ids = new_pin_ids

    def _handle_new_pin(self, message_id, pins):
        """处理新增Pin消息"""
        print(f"[Pin监控] 发现新Pin消息: {message_id}")
        
        # 获取Pin信息
        pin_data = next((p for p in pins if p.get("message_id") == message_id), None)
        if not pin_data:
            return
        
        operator_id = pin_data.get("operator_id")  # 修正: 根据API文档,operator_id是字符串,不是字典
        create_time = pin_data.get("create_time")
        
        # 获取消息详情
        message_details = self.get_message_details(message_id)
        if not message_details:
            return
        
        sender_id = message_details.get("sender_id")
        msg_type = message_details.get("message_type")
        
        # 获取用户名称
        sender_name = self.get_user_name(sender_id)
        operator_name = self.get_user_name(operator_id)
        
        # 处理附件(图片和文件)
        file_tokens = []
        
        # 1. 处理富文本中的嵌入图片
        image_keys = message_details.get("image_keys", [])
        if image_keys:
            for img_key in image_keys:
                print(f"  > [Pin附件] 正在处理富文本嵌入图片: {img_key}")
                file_token = self._download_and_upload_resource(message_id, img_key, "image", f"{img_key}.png")
                if file_token:
                    file_tokens.append(file_token)
        
        # 2. 处理独立的图片消息
        if msg_type == "image" and message_details.get("image_key"):
            img_key = message_details.get("image_key")
            print(f"  > [Pin附件] 正在处理图片消息: {img_key}")
            file_token = self._download_and_upload_resource(message_id, img_key, "image", f"{img_key}.png")
            if file_token:
                file_tokens.append(file_token)
        
        # 3. 处理文件消息
        elif msg_type == "file" and message_details.get("file_key"):
            file_key = message_details.get("file_key")
            file_name = message_details.get("file_name", "file")
            print(f"  > [Pin附件] 正在处理文件消息: {file_name}")
            file_token = self._download_and_upload_resource(message_id, file_key, "file", file_name)
            if file_token:
                file_tokens.append(file_token)
        
        # 格式化时间为文本(YYYY-MM-DD HH:MM:SS)
        pin_time_str = datetime.fromtimestamp(int(create_time) / 1000).strftime("%Y-%m-%d %H:%M:%S")
        msg_create_time = message_details.get("create_time")
        msg_create_time_str = datetime.fromtimestamp(int(msg_create_time) / 1000).strftime("%Y-%m-%d %H:%M:%S")
        archive_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建Pin信息
        pin_info = {
            "message_id": message_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "operator_id": operator_id,
            "operator_name": operator_name,
            "pin_time": pin_time_str,  # 格式化的时间文本
            "message_type": msg_type,
            "content": message_details.get("content"),
            "create_time": msg_create_time_str,  # 格式化的时间文本
            "archive_time": archive_time_str,  # 格式化的时间文本
            "file_tokens": file_tokens  # 附件列表
        }
        
        print(f"[Pin监控] 消息发送者: {sender_name}, Pin操作人: {operator_name}")
        
        # 1. 发送群内提醒
        self.send_pin_notification(message_id, pin_info)
        
        # 2. 归档到Bitable
        if hasattr(self.storage, 'archive_pin_message'):
            self.storage.archive_pin_message(pin_info)
        
        # 3. 更新被Pin次数统计
        if hasattr(self.storage, 'increment_pin_count'):
            self.storage.increment_pin_count(sender_id, sender_name)

    def _download_and_upload_resource(self, message_id, file_key, resource_type, file_name):
        """
        下载消息资源并上传到飞书云盘
        
        Args:
            message_id: 消息ID
            file_key: 文件key
            resource_type: 资源类型(image/file)
            file_name: 文件名
            
        Returns:
            dict: 上传后的file_token信息,失败返回None
        """
        # 下载资源
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}"
        params = {"type": resource_type}
        headers = {
            "Authorization": f"Bearer {self.auth.get_tenant_access_token()}"
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            if response.status_code != 200:
                print(f"  > [Pin附件] ❌ 下载资源失败: {response.status_code}")
                return None
            
            file_content = response.content
            
            # 上传到飞书云盘
            return self._upload_to_drive(file_content, file_name)
        except Exception as e:
            print(f"  > [Pin附件] ❌ 下载资源异常: {e}")
            return None

    def _upload_to_drive(self, file_content, file_name):
        """上传文件到飞书云盘"""
        url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        
        app_token = os.getenv('BITABLE_APP_TOKEN')
        form_data = {
            'file_name': file_name,
            'parent_type': 'bitable_file',
            'parent_node': app_token,
            'size': str(len(file_content))
        }
        
        files = {'file': (file_name, file_content)}
        upload_headers = {
            "Authorization": f"Bearer {self.auth.get_tenant_access_token()}"
        }
        
        try:
            response = requests.post(url, headers=upload_headers, data=form_data, files=files, timeout=60)
            result = response.json()
            
            if result.get('code') == 0:
                file_token = result.get('data', {}).get('file_token')
                if file_token:
                    print(f"  > [Pin附件] ✅ 附件已上传: {file_token}")
                    return {
                        "file_token": file_token,
                        "name": file_name,
                        "size": len(file_content),
                        "type": "file"
                    }
            else:
                print(f"  > [Pin附件] ❌ 上传失败: {result}")
                return None
        except Exception as e:
            print(f"  > [Pin附件] ❌ 上传异常: {e}")
            return None

    def _handle_unpin(self, message_id):
        """处理取消Pin消息（静默删除）"""
        print(f"[Pin监控] 检测到取消Pin: {message_id}")
        
        # 从缓存获取消息详情
        message_details = self.pin_details_cache.get(message_id)
        if message_details:
            sender_id = message_details.get("sender_id")
            sender_name = self.get_user_name(sender_id)
            
            # 减少被Pin次数
            if hasattr(self.storage, 'decrement_pin_count'):
                self.storage.decrement_pin_count(sender_id, sender_name)
        
        # 从归档表删除记录
        if hasattr(self.storage, 'delete_pin_message'):
            self.storage.delete_pin_message(message_id)
        
        print(f"[Pin监控] ✅ 已删除Pin归档记录: {message_id}")

    def _monitor_loop(self):
        """监控循环（后台线程）"""
        print(f"[Pin监控] 🚀 开始监控，轮询间隔: {self.interval}秒")
        
        while self.running:
            try:
                self.check_pin_changes()
            except Exception as e:
                print(f"[Pin监控] ❌ 监控循环异常: {e}")
            
            # 等待下一次轮询
            time.sleep(self.interval)

    def start(self):
        """启动Pin监控"""
        if self.running:
            print("[Pin监控] ⚠️ 监控已在运行中")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("[Pin监控] ✅ Pin监控已启动")

    def stop(self):
        """停止Pin监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("[Pin监控] 🛑 Pin监控已停止")
