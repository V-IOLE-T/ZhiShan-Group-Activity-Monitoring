import os
import json
from dotenv import load_dotenv
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from datetime import datetime

# 导入现有模块
from auth import FeishuAuth
from calculator import MetricsCalculator
from storage import BitableStorage
from collector import MessageCollector

load_dotenv()

# 初始化配置
APP_ID = os.getenv('APP_ID')
APP_SECRET = os.getenv('APP_SECRET')
CHAT_ID = os.getenv('CHAT_ID')

# 初始化组件
auth = FeishuAuth()
storage = BitableStorage(auth)
collector = MessageCollector(auth)
calculator = MetricsCalculator([])

# 用户昵称缓存
user_name_cache = {}

# 事件去重缓存
processed_events = set()

def get_cached_nickname(user_id):
    """获取缓存的昵称，如果不存在则从 API 获取并更新缓存"""
    if not user_id:
        return user_id
        
    if user_id not in user_name_cache:
        print(f"正在获取用户 {user_id} 的群备注...")
        names = collector.get_user_names([user_id])
        if names:
            user_name_cache.update(names)
    
    return user_name_cache.get(user_id, user_id)

def do_p2_im_message_receive_v1(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    """处理接收消息 v2.0 事件"""
    # 0. 事件去重
    event_id = data.header.event_id
    if event_id in processed_events:
        return
    processed_events.add(event_id)
    
    # 限制去重缓存大小
    if len(processed_events) > 1000:
        processed_events.clear()

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
    except Exception as e:
        print(f"❌ 实时更新失败: {e}")

def do_p2_im_message_reaction_created_v1(data: lark.im.v1.P2ImMessageReactionCreatedV1) -> None:
    """处理表情回复事件（点赞）"""
    # 0. 事件去重
    event_id = data.header.event_id
    if event_id in processed_events:
        return
    processed_events.add(event_id)
    
    # 限制去重缓存大小
    if len(processed_events) > 1000:
        processed_events.clear()
    
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
    print("="*50)

    cli.start()

if __name__ == "__main__":
    main()
