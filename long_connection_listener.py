import os
import json
from dotenv import load_dotenv
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from datetime import datetime

# 导入现有模块
from auth import FeishuAuth
from calculator import MetricsCalculator
from storage import BitableStorage, MessageArchiveStorage
from collector import MessageCollector
from config import CACHE_USER_NAME_SIZE, CACHE_EVENT_SIZE, TOPIC_ACTIVE_DAYS, TOPIC_SILENT_DAYS
from pin_monitor import PinMonitor
from utils import LRUCache

load_dotenv()

# 初始化配置
APP_ID = os.getenv('APP_ID')
APP_SECRET = os.getenv('APP_SECRET')
CHAT_ID = os.getenv('CHAT_ID')

# 初始化组件
auth = FeishuAuth()
storage = BitableStorage(auth)
archive_storage = MessageArchiveStorage(auth)
collector = MessageCollector(auth)
calculator = MetricsCalculator([])


# 用户昵称缓存 - 使用LRU防止内存泄漏
user_name_cache = LRUCache(capacity=CACHE_USER_NAME_SIZE)

# 事件去重缓存 - 使用LRU防止内存泄漏
processed_events = LRUCache(capacity=CACHE_EVENT_SIZE)

def get_cached_nickname(user_id):
    """获取缓存的昵称，如果不存在则从 API 获取并更新缓存"""
    if not user_id:
        return user_id
        
    cached_name = user_name_cache.get(user_id)
    if cached_name:
        return cached_name
    
    print(f"正在获取用户 {user_id} 的群备注...")
    names = collector.get_user_names([user_id])
    if names:
        for uid, name in names.items():
            user_name_cache.set(uid, name)
    
    return user_name_cache.get(user_id, user_id)

def do_p2_im_message_receive_v1(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    """处理接收消息 v2.0 事件"""
    # 0. 事件去重
    event_id = data.header.event_id
    if event_id in processed_events:
        return
    processed_events.set(event_id, True)  # LRU会自动管理容量，无需手动清理

    event = data.event
    message = event.message
    sender = event.sender
    
    # 获取发送者 OpenID
    sender_id = sender.sender_id.open_id
    if not sender_id:
        return

    # [V3-LOG] 收到事件原始追踪
    now_str = datetime.now().strftime('%H:%M:%S')
    print(f"\n[V3-LOG] [{now_str}] 收到新消息=========================")

    # 1. 验证群聊
    if message.chat_id != CHAT_ID:
        print(f"  > [验证] 消息来自非目标群组 (ID: {message.chat_id})，跳过统计")
        return

    # 2. 解析内容
    content_str = message.content
    char_count = calculator._extract_text_length(content_str)
    
    print(f"  > 消息ID: {message.message_id}")
    print(f"  > 父ID (parent_id): {message.parent_id or 'None'}")
    print(f"  > 根ID (root_id): {message.root_id or 'None'}")
    
    # 3. 获取发送者昵称
    user_name = get_cached_nickname(sender_id)

    # 4. 构建指标增量
    metrics_delta = {
        "message_count": 1,
        "char_count": char_count,
        "reply_received": 0,
        "mention_received": 0,
        "topic_initiated": 1 if not message.root_id else 0
    }

    # 5. 更新多维表格
    try:
        print(f"实时更新: {user_name} (字数: {char_count})")
        storage.update_or_create_record(sender_id, user_name, metrics_delta)
        
        # 6. 特殊逻辑：处理被回复的情况
        parent_id = message.parent_id
        root_id = message.root_id
        already_credited_ids = set() # 记录本消息中已经获得“被回复”积分的人
        
        if parent_id:
            # 识别目标用户 ID (target_parent_id)
            target_parent_id = None
            
            # 启发式逻辑：在话题群中，parent_id 和 root_id 通常相同且指向话题头
            if parent_id == root_id and message.mentions:
                target_parent_id = message.mentions[0].id.open_id
                print(f"  > [探测] 识别到话题嵌套回复: 使用首个艾特对象 {target_parent_id}")
            else:
                # 普通群或直接回复话题，使用父消息发送者
                target_parent_id = collector.get_message_sender(parent_id)
            
            if target_parent_id:
                # 获取被回复者昵称
                target_user_name = get_cached_nickname(target_parent_id)
                print(f"  > [更新] 增加被回复数给: {target_user_name}")
                storage.update_or_create_record(target_parent_id, target_user_name, {"reply_received": 1})
                already_credited_ids.add(target_parent_id)

        # 7. 处理被 @ 的人
        if message.mentions:
            for mention in message.mentions:
                mentioned_id = mention.id.open_id
                if mentioned_id:
                    # 如果该用户刚才已经因为“被回复”加过分了，这次 @ 就跳过，避免重复计费
                    if mentioned_id in already_credited_ids:
                        print(f"  > [跳过] {mentioned_id} 已在本次统计中作为被回复者，跳过艾特计费")
                        continue
                        
                    mentioned_name = get_cached_nickname(mentioned_id)
                    print(f"  > [更新] 增加被艾特数给: {mentioned_name}")
                    storage.update_or_create_record(mentioned_id, mentioned_name, {"mention_received": 1})
        
        print("✅ 实时同步圆满成功")
        
        # 8. 归档消息到新表
        try:
            archive_message_logic(message, sender_id, user_name)
        except Exception as e:
            print(f"  > [归档] ⚠️ 归档逻辑执行失败: {e}")

    except Exception as e:
        print(f"❌ 实时更新失败: {e}")

def _process_message_attachments(message, message_id: str) -> list:
    """
    处理消息附件（图片和文件）

    Args:
        message: 消息对象
        message_id: 消息ID

    Returns:
        file_tokens列表，包含上传后的附件信息
    """
    file_tokens = []

    # 提取纯文本和嵌入的图片 keys
    text_content, embedded_image_keys = MetricsCalculator.extract_text_from_content(message.content)

    # 处理富文本中嵌入的图片
    if embedded_image_keys:
        for img_key in embedded_image_keys:
            print(f"  > [附件] 正在处理富文本嵌入图片: {img_key}")
            file_bin = archive_storage.download_message_resource(message_id, img_key, "image")
            if file_bin:
                attachment_obj = archive_storage.upload_file_to_drive(file_bin, f"{img_key}.png")
                if attachment_obj:
                    file_tokens.append(attachment_obj)

    # 解析content获取文件信息
    try:
        content_obj = json.loads(message.content) if isinstance(message.content, str) else message.content
    except (json.JSONDecodeError, ValueError):
        content_obj = {}

    # 处理独立的图片消息
    if message.message_type == "image":
        file_key = content_obj.get("image_key")
        if file_key:
            print(f"  > [附件] 正在处理图片消息: {file_key}")
            file_bin = archive_storage.download_message_resource(message_id, file_key, "image")
            if file_bin:
                attachment_obj = archive_storage.upload_file_to_drive(file_bin, f"{file_key}.png")
                if attachment_obj:
                    file_tokens.append(attachment_obj)

    # 处理文件消息
    elif message.message_type == "file":
        file_key = content_obj.get("file_key")
        file_name = content_obj.get("file_name", "file")
        if file_key:
            print(f"  > [附件] 正在处理文件消息: {file_name}")
            file_bin = archive_storage.download_message_resource(message_id, file_key, "file")
            if file_bin:
                attachment_obj = archive_storage.upload_file_to_drive(file_bin, file_name)
                if attachment_obj:
                    file_tokens.append(attachment_obj)

    return file_tokens, text_content


def _build_archive_fields(message, sender_id: str, user_name: str,
                          text_content: str, file_tokens: list,
                          month_str: str, timestamp_ms: int) -> dict:
    """
    构建消息归档字段

    Args:
        message: 消息对象
        sender_id: 发送者ID
        user_name: 发送者姓名
        text_content: 消息文本内容
        file_tokens: 附件列表
        month_str: 统计月份
        timestamp_ms: 时间戳（毫秒）

    Returns:
        归档字段字典
    """
    # 构建消息链接
    message_link = {
        "link": f"https://applink.feishu.cn/client/chat/open?openChatId={CHAT_ID}&messageId={message.message_id}",
        "text": "查看消息"
    }

    archive_fields = {
        "消息ID": message.message_id,
        "话题ID": message.root_id or message.message_id,
        "父消息ID": message.parent_id or "",
        "发送者": [{"id": sender_id}],
        "发送者姓名": user_name,
        "消息内容": text_content,
        "消息类型": message.message_type,
        "发送时间": timestamp_ms,
        "统计月份": month_str,
        "消息链接": message_link,
    }

    # 添加附件信息
    if file_tokens:
        archive_fields["附件信息"] = file_tokens

    # 添加@的人
    if message.mentions:
        mention_names = [m.name for m in message.mentions]
        archive_fields["@的人"] = ", ".join(mention_names)

    return archive_fields


def _get_topic_status(last_reply_time_ms: int) -> str:
    """
    根据最后回复时间判断话题状态

    Args:
        last_reply_time_ms: 最后回复时间戳（毫秒）

    Returns:
        话题状态：活跃/沉默/冷却
    """
    if not last_reply_time_ms:
        return "活跃"

    now = datetime.now()
    last_reply_time = datetime.fromtimestamp(last_reply_time_ms / 1000)
    days_since_last_reply = (now - last_reply_time).days

    if days_since_last_reply <= TOPIC_ACTIVE_DAYS:
        return "活跃"
    elif days_since_last_reply <= TOPIC_SILENT_DAYS:
        return "沉默"
    else:
        return "冷却"


def _update_topic_summary(message, sender_id: str, user_name: str,
                          text_content: str, root_id: str,
                          month_str: str, timestamp_ms: int):
    """
    更新或创建话题汇总

    Args:
        message: 消息对象
        sender_id: 发送者ID
        user_name: 发送者姓名
        text_content: 消息文本内容
        root_id: 话题根消息ID
        month_str: 统计月份
        timestamp_ms: 时间戳（毫秒）
    """
    topic_record = archive_storage.get_topic_by_id(root_id)

    # 构建话题链接
    topic_link = {
        "link": f"https://applink.feishu.cn/client/chat/open?openChatId={CHAT_ID}&messageId={root_id}",
        "text": "查看话题"
    }

    if not topic_record:
        # 创建新话题
        summary_fields = {
            "话题ID": root_id,
            "话题标题": text_content,
            "发起人": [{"id": sender_id}],
            "发起人姓名": user_name,
            "创建时间": timestamp_ms,
            "最后回复时间": timestamp_ms,
            "回复数": 0 if not message.root_id else 1,
            "参与人数": 1,
            "参与者": user_name,
            "话题状态": "活跃",
            "统计月份": month_str,
            "话题链接": topic_link
        }
        archive_storage.update_or_create_topic(root_id, summary_fields, is_new=True)
    else:
        # 更新已有话题
        old_fields = topic_record['fields']

        # 更新参与者列表
        participants = set()
        participants_raw = old_fields.get("参与者", "")

        if isinstance(participants_raw, list):
            for item in participants_raw:
                if isinstance(item, dict):
                    name = item.get('text', '')
                    if name:
                        participants.add(name)
                elif isinstance(item, str) and item:
                    participants.add(item)
        elif isinstance(participants_raw, str) and participants_raw:
            for name in participants_raw.split(", "):
                if name.strip():
                    participants.add(name.strip())

        participants.add(user_name)

        # 计算话题状态
        topic_status = _get_topic_status(timestamp_ms)

        summary_fields = {
            "最后回复时间": timestamp_ms,
            "回复数": int(old_fields.get("回复数", 0)) + 1,
            "参与人数": len(participants),
            "参与者": ", ".join(participants),
            "话题状态": topic_status
        }
        archive_storage.update_or_create_topic(root_id, summary_fields, is_new=False)


def archive_message_logic(message, sender_id, user_name):
    """
    处理消息归档和话题汇总（重构版）

    将消息保存到归档表，并更新话题汇总信息

    Args:
        message: 消息对象
        sender_id: 发送者ID
        user_name: 发送者姓名
    """
    now = datetime.now()
    month_str = now.strftime("%Y-%m")
    timestamp_ms = int(now.timestamp() * 1000)

    # 1. 处理附件
    file_tokens, text_content = _process_message_attachments(message, message.message_id)

    # 2. 构建归档字段
    archive_fields = _build_archive_fields(
        message, sender_id, user_name,
        text_content, file_tokens,
        month_str, timestamp_ms
    )

    # 3. 保存到消息归档表
    archive_storage.save_message(archive_fields)

    # 4. 更新话题汇总
    root_id = message.root_id or message.message_id
    _update_topic_summary(
        message, sender_id, user_name,
        text_content, root_id,
        month_str, timestamp_ms
    )


def do_p2_im_message_reaction_created_v1(data: lark.im.v1.P2ImMessageReactionCreatedV1) -> None:
    """处理表情回复事件（点赞）"""
    # 0. 事件去重
    event_id = data.header.event_id
    if event_id in processed_events:
        return
    processed_events.set(event_id, True)  # LRU会自动管理容量，无需手动清理
    
    event = data.event
    
    # 获取操作者ID（点赞的人）
    operator_id = event.user_id.open_id if event.user_id else None
    if not operator_id:
        return
    
    # 获取消息ID
    message_id = event.message_id
    if not message_id:
        return
    
    # [V3-LOG] 表情回复事件追踪
    now_str = datetime.now().strftime('%H:%M:%S')
    print(f"\n[V3-LOG] [{now_str}] 收到表情回复事件===================")
    print(f"  > 消息ID: {message_id}")
    print(f"  > 操作者ID: {operator_id}")
    
    try:
        # 1. 获取消息的发送者（被点赞的人）
        message_sender_id = collector.get_message_sender(message_id)
        if not message_sender_id:
            print(f"  > [跳过] 无法获取消息发送者")
            return
        
        # 2. 获取昵称
        operator_name = get_cached_nickname(operator_id)
        receiver_name = get_cached_nickname(message_sender_id)
        
        print(f"  > 点赞者: {operator_name}")
        print(f"  > 被点赞者: {receiver_name}")
        
        # 3. 更新点赞者的"点赞数"
        storage.update_or_create_record(
            user_id=operator_id,
            user_name=operator_name,
            metrics_delta={"reaction_given": 1}
        )
        
        # 4. 更新被点赞者的"被点赞数"
        if message_sender_id != operator_id:  # 避免自己给自己点赞的情况
            storage.update_or_create_record(
                user_id=message_sender_id,
                user_name=receiver_name,
                metrics_delta={"reaction_received": 1}
            )
        else:
            print(f"  > [跳过] 用户给自己点赞")
        
        print("✅ 表情回复统计成功")
        
    except Exception as e:
        print(f"❌ 表情回复统计失败: {e}")


# 初始化事件处理器
event_handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
    .register_p2_im_message_reaction_created_v1(do_p2_im_message_reaction_created_v1) \
    .build()

def main():
    if not APP_ID or not APP_SECRET:
        print("❌ 错误: 请在 .env 中配置 APP_ID 和 APP_SECRET")
        return

    # 初始化Pin监控(可选,需要配置PIN_TABLE_ID)
    pin_monitor = None
    pin_table_id = os.getenv('PIN_TABLE_ID')
    pin_interval = int(os.getenv('PIN_MONITOR_INTERVAL', 30))  # 默认30秒
    
    if pin_table_id:
        print(f"🔍 Pin监控已启用 (轮询间隔: {pin_interval}秒)")
        pin_monitor = PinMonitor(auth, storage, CHAT_ID, interval=pin_interval)
        pin_monitor.start()
    else:
        print("ℹ️  Pin监控未启用 (需要在.env中配置PIN_TABLE_ID)")

    # 初始化长连接客户端
    cli = lark.ws.Client(
        APP_ID, 
        APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO
    )

    print("="*50)
    print("🚀 飞书实时监听 [V3-STABLE] 启动")
    print(f"系统时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标群组: {CHAT_ID}")
    print("特性: 超时重试已开启, 自动去重, 话题模式增强, 艾特去重")
    if pin_monitor:
        print("特性: Pin消息监控已启动")
    print("="*50)

    try:
        cli.start()
    except KeyboardInterrupt:
        print("\n🛑 收到退出信号，正在关闭...")
        if pin_monitor:
            pin_monitor.stop()
        print("✅ 程序已安全退出")

if __name__ == "__main__":
    main()

