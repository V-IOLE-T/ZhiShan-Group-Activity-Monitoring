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
from reply_card import DocCardProcessor
from utils import LRUCache
from storage import DocxStorage
from message_renderer import MessageToDocxConverter
from pin_scheduler import start_pin_scheduler, stop_pin_scheduler

load_dotenv()

# 初始化配置
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
CHAT_ID = os.getenv("CHAT_ID")
ARCHIVE_DOC_TOKEN = os.getenv("ARCHIVE_DOC_TOKEN")

# 初始化组件
auth = FeishuAuth()
storage = BitableStorage(auth)
archive_storage = MessageArchiveStorage(auth)
collector = MessageCollector(auth)
calculator = MetricsCalculator([])
doc_processor = DocCardProcessor(auth)
docx_storage = DocxStorage(auth)
docx_converter = MessageToDocxConverter(docx_storage)


# 标签映射配置
TAG_MAPPING = {
    "问答": os.getenv("DOC_TOKEN_TAG_QA"),
    "打卡": os.getenv("DOC_TOKEN_TAG_CHECKIN"),
    "雅思": os.getenv("DOC_TOKEN_TAG_ENGLISH"), 
    "英语学习": os.getenv("DOC_TOKEN_TAG_ENGLISH"),
    "雅思/英语学习": os.getenv("DOC_TOKEN_TAG_ENGLISH"),
    "AI实用分享": os.getenv("DOC_TOKEN_TAG_AI"),
    "写作运营": os.getenv("DOC_TOKEN_TAG_OPS"),
    "沟通场景/技巧": os.getenv("DOC_TOKEN_TAG_COMM"),
    "个人思考": os.getenv("DOC_TOKEN_TAG_THINKING"),
    "攻略分享": os.getenv("DOC_TOKEN_TAG_GUIDE"),
}

def get_target_doc_token(message):
    """根据消息内容获取目标文档 Token"""
    
    # 1. 确定要检查的内容
    # 如果是回复消息，需要检查根消息的内容来确定归档位置
    check_content_str = message.content
    is_reply = bool(message.parent_id or message.root_id)
    
    if is_reply and message.root_id:
        # 尝试获取根消息内容
        # print(f"  > [路由] 这是一条回复消息，正在获取根消息 {message.root_id} 以确定标签...")
        try:
            root_msg = collector.get_message_detail(message.root_id)
            if root_msg:
                # root_msg['body']['content'] 是 JSON 字符串
                check_content_str = root_msg.get("body", {}).get("content", "")
        except Exception as e:
            print(f"  > [路由] 获取根消息失败: {e}")
            
    # 2. 提取纯文本用于标签匹配
    # 使用 MetricsCalculator 提取文本，或者简单解析
    plain_text = ""
    try:
        # 尝试复用现有的提取逻辑，或者简单实现
        if check_content_str:
            # 简单解析：尝试提取 text 字段
            try:
                content_obj = json.loads(check_content_str)
                # 递归提取所有 text 字段
                def extract_text(obj):
                    texts = []
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k == 'text' and isinstance(v, str):
                                texts.append(v)
                            else:
                                texts.extend(extract_text(v))
                    elif isinstance(obj, list):
                        for item in obj:
                            texts.extend(extract_text(item))
                    return texts
                
                texts = extract_text(content_obj)
                plain_text = " ".join(texts)
            except:
                plain_text = check_content_str # Fallback
    except Exception as e:
        print(f"  > [路由] 解析文本失败: {e}")
        plain_text = check_content_str

    # 3. 检查标签
    # 默认使用 ARCHIVE_DOC_TOKEN (如果没有配置，且没匹配到标签，则返回 None)
    target_token = ARCHIVE_DOC_TOKEN or None
    matched_tag = "默认"
    
    if plain_text:
        # 优先匹配长标签
        sorted_tags = sorted(TAG_MAPPING.keys(), key=len, reverse=True)
        
        for tag in sorted_tags:
            token = TAG_MAPPING.get(tag)
            if not token: continue 
            
            # 检查 #标签
            search_key = f"#{tag}"
            if search_key in plain_text:
                target_token = token
                matched_tag = tag
                break
                
    # print(f"  > [路由] 标签: {matched_tag} -> 文档: {target_token}")
    return target_token, matched_tag


# 用户昵称缓存 - 使用LRU防止内存泄漏
user_name_cache = LRUCache(capacity=CACHE_USER_NAME_SIZE)

# 事件去重缓存 - 使用LRU防止内存泄漏
processed_events = LRUCache(capacity=CACHE_EVENT_SIZE)

# 批量更新配置
BATCH_UPDATE_THRESHOLD = 3  # 每 3 条消息更新一次
message_counter = 0
pending_updates = {}  # {user_id: {"user_name": str, "metrics": dict}}


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


def accumulate_metrics(user_id: str, user_name: str, metrics_delta: dict):
    """累积用户指标到待更新字典"""
    global pending_updates
    
    if user_id not in pending_updates:
        pending_updates[user_id] = {
            "user_name": user_name,
            "metrics": {
                "message_count": 0,
                "char_count": 0,
                "reply_received": 0,
                "mention_received": 0,
                "topic_initiated": 0,
            }
        }
    
    # 累加指标
    for key, value in metrics_delta.items():
        if key in pending_updates[user_id]["metrics"]:
            pending_updates[user_id]["metrics"][key] += value


def flush_pending_updates():
    """批量更新所有待处理的用户统计"""
    global pending_updates
    
    if not pending_updates:
        return
    
    print(f"📊 批量更新 {len(pending_updates)} 个用户的统计数据...")
    
    for user_id, data in pending_updates.items():
        try:
            storage.update_or_create_record(
                user_id, 
                data["user_name"], 
                data["metrics"]
            )
        except Exception as e:
            print(f"❌ 更新 {data['user_name']} 失败: {e}")
    
    pending_updates = {}
    print("✅ 批量更新完成")


def do_p2_im_message_receive_v1(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    """处理接收消息 v2.0 事件"""
    from health_monitor import update_event_processed
    
    event = data.event
    message = event.message
    sender = event.sender

    # [V3-LOG] 绝对最前置日志：只要飞书发了，这里就一定有输出
    now_str = datetime.now().strftime("%H:%M:%S")
    print(f"\n[V3-LOG] [{now_str}] 收到原始事件通知 =========================")
    print(f"  > 事件ID: {data.header.event_id}")
    print(f"  > 消息类型: {message.message_type}")
    print(f"  > 原始内容: {message.content[:200]}...")
    
    # 更新健康监控状态
    update_event_processed("message")

    # 0. 事件去重
    event_id = data.header.event_id
    if event_id in processed_events:
        print(f"  > [拦截] 该事件已处理过，跳过 (去重)")
        return
    processed_events.set(event_id, True)

    # 获取发送者 OpenID
    sender_id = sender.sender_id.open_id
    if not sender_id:
        print(f"  > [拦截] 无法获取 sender_id")
        return

    # 1. 识别聊天类型并执行过滤
    chat_type = message.chat_type  # 'p2p' 或 'group'
    is_p2p = (chat_type == "p2p")
    is_target_group = (chat_type == "group" and message.chat_id == CHAT_ID)

    print(f"  > [分析] 会话类型: {chat_type}, 是否单聊: {is_p2p}")

    # 情况 A：如果是单聊（P2P），处理文档链接或纯文本
    if is_p2p:
        print(f"  > [单聊] 收到单聊消息，准备处理...")
        try:
            # 提取消息文本内容
            message_text = ""
            if message.message_type == "text":
                try:
                    content_obj = json.loads(message.content)
                    message_text = content_obj.get("text", "")
                except:
                    message_text = message.content
            
            # 检测是否包含文档链接
            has_doc_link = doc_processor.extract_token(message_text)
            
            if has_doc_link:
                # 处理文档链接，发送卡片样式图片（带绿色标题）
                print(f"  > [单聊] 检测到文档链接，正在生成卡片...")
                doc_processor.process_and_reply(message_text, message.chat_id)
            elif message_text.strip():
                # 纯文本消息，生成简洁图片（无标题栏）
                print(f"  > [单聊] 收到纯文本: {message_text[:50]}...")
                try:
                    from reply_card.image_generator import DocImageGenerator
                    generator = DocImageGenerator()
                    # 纯文本作为内容，标题为空
                    image_data = generator.generate_doc_image("", message_text)
                    doc_processor._send_image_reply(message.chat_id, image_data)
                    print(f"  > [单聊] ✅ 纯文本图片发送成功")
                except Exception as e:
                    print(f"  > [单聊] ❌ 图片生成失败: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"  > [单聊] 消息内容为空或非文本类型，跳过")
        except Exception as e:
            print(f"  > [单聊] 处理异常: {e}")
            import traceback
            traceback.print_exc()
        
        return  # 单聊处理完毕，不参与群组统计逻辑

    # 情况 B：如果是非目标群组，跳过
    if not is_target_group:
        return

    # 情况 C：目标群组的消息，执行归档和统计
    
    # [新增] 自动归档群消息到文档
    # 尝试获取目标文档 Token，如果既没匹配标签也没配置默认文档，则返回 None
    target_doc_token, matched_tag = get_target_doc_token(message)

    if target_doc_token:
        try:
            print(f"  > [归档] 正在采集群消息到文档 {target_doc_token}...")
            
            # ... (中间代码保持不变，通过省略号或不需要改动) ... 
            # 实际上由于 replace_file_content 需要连续块，我必须完整包含

            # 获取发送者昵称
            # sender.sender_id 可能有多种格式，需要正确提取
            sender_id = None
            if sender and sender.sender_id:
                # 尝试获取 user_id 或 open_id
                sender_id = getattr(sender.sender_id, 'user_id', None) or \
                           getattr(sender.sender_id, 'open_id', None) or \
                           getattr(sender.sender_id, 'union_id', None)
            
            if sender_id:
                sender_nickname = get_cached_nickname(sender_id)
            else:
                sender_nickname = "未知用户"
            
            # 格式化发送时间
            create_time = message.create_time
            if create_time:
                # create_time 是毫秒时间戳
                send_time = datetime.fromtimestamp(int(create_time) / 1000).strftime("%Y-%m-%d %H:%M:%S")
            else:
                send_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 判断是否是回复消息（有 parent_id 或 root_id 就是回复）
            is_reply = bool(message.parent_id or message.root_id)
            
            # [路由] 获取目标归档文档 Token (已在上方获取)
            print(f"  > [归档] 目标文档: {target_doc_token} (Tag: {matched_tag})")
            
            # 新增: 跳过无标签消息
            if matched_tag == "默认":
                print(f"  > [归档] 跳过无标签消息")
            else:
                # 获取被回复者的昵称（仅针对嵌套回复）
                parent_sender_nickname = None
                if is_reply and message.parent_id and message.root_id and message.parent_id != message.root_id:
                    try:
                        # 获取父消息详情
                        parent_msg = collector.get_message_detail(message.parent_id)
                        if parent_msg:
                            # 提取父消息发送者ID
                            parent_sender = parent_msg.get("sender", {})
                            parent_sender_id_obj = parent_sender.get("sender_id", {})
                            # API 返回的 sender_id 对象可能是字典
                            parent_uid = parent_sender_id_obj.get("user_id") or \
                                       parent_sender_id_obj.get("open_id") or \
                                       parent_sender_id_obj.get("union_id")
                            
                            if parent_uid:
                                parent_sender_nickname = get_cached_nickname(parent_uid)
                    except Exception as e:
                        print(f"  > [归档] 获取被回复者信息失败: {e}")

                # 转换内容（带发送者和时间，以及是否是回复）
                # 如果匹配到了具体标签（非"默认"），则通知 convert 移除该标签
                tag_to_remove = matched_tag if matched_tag != "默认" else None
                
                blocks = docx_converter.convert(
                    message.content, message.message_id, target_doc_token,
                    sender_name=sender_nickname, send_time=send_time, 
                    is_reply=is_reply, parent_sender_name=parent_sender_nickname,
                    remove_tag=tag_to_remove
                )
                # 写入文档（回复消息需要插入在分割线之前）
                docx_storage.add_blocks(target_doc_token, blocks, insert_before_divider=is_reply)
                print(f"  > [归档] ✅ 群消息已同步 (标签: {matched_tag}, Doc: {target_doc_token[-6:]})")
        except Exception as e:
            print(f"  > [归档] ❌ 同步失败: {e}")
            import traceback
            traceback.print_exc()

    content_str = message.content
    char_count = calculator._extract_text_length(content_str)

    print(f"  > 消息ID: {message.message_id}")
    print(f"  > 父ID (parent_id): {message.parent_id or 'None'}")
    print(f"  > 根ID (root_id): {message.root_id or 'None'}")

    # 3. 获取发送者昵称
    user_name = get_cached_nickname(sender_id)

    # [Bitable归档] 已禁用: 归档消息到 Bitable (双表格模式)
    # try:
    #     file_tokens_for_db, text_content_for_db = _process_message_attachments(message, message.message_id)
    #     create_time_ms = int(message.create_time)
    #     dt_object = datetime.fromtimestamp(create_time_ms / 1000)
    #     month_str = dt_object.strftime("%Y-%m")
    #     archive_fields = _build_archive_fields(...)
    #     if hasattr(archive_storage, "save_message"):
    #         archive_storage.save_message(archive_fields)
    #     _update_topic_summary(...)
    # except Exception as e:
    #     print(f"  > [Bitable] ❌ 归档失败: {e}")

    # 4. 构建指标增量
    metrics_delta = {
        "message_count": 1,
        "char_count": char_count,
        "reply_received": 0,
        "mention_received": 0,
        "topic_initiated": 1 if not message.root_id else 0,
    }

    # 5. 累积到批量更新字典 (替代原来的实时更新)
    global message_counter
    accumulate_metrics(sender_id, user_name, metrics_delta)

    # 6. 特殊逻辑：处理被回复的情况
    parent_id = message.parent_id
    root_id = message.root_id
    already_credited_ids = set()  # 记录本消息中已经获得"被回复"积分的人

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
            # 获取被回复者昵称并累积
            target_user_name = get_cached_nickname(target_parent_id)
            print(f"  > [更新] 增加被回复数给: {target_user_name}")
            accumulate_metrics(target_parent_id, target_user_name, {"reply_received": 1})
            already_credited_ids.add(target_parent_id)

    # 7. 处理被 @ 的人
    if message.mentions:
        for mention in message.mentions:
            mentioned_id = mention.id.open_id
            if mentioned_id:
                # 如果该用户刚才已经因为"被回复"加过分了，这次 @ 就跳过，避免重复计费
                if mentioned_id in already_credited_ids:
                    print(f"  > [跳过] {mentioned_id} 已在本次统计中作为被回复者，跳过艾特计费")
                    continue

                mentioned_name = get_cached_nickname(mentioned_id)
                print(f"  > [更新] 增加被艾特数给: {mentioned_name}")
                accumulate_metrics(mentioned_id, mentioned_name, {"mention_received": 1})

    # 8. 检查是否需要批量更新
    message_counter += 1
    if message_counter >= BATCH_UPDATE_THRESHOLD:
        flush_pending_updates()
        message_counter = 0

    print("✅ 消息处理完成")


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
        content_obj = (
            json.loads(message.content) if isinstance(message.content, str) else message.content
        )
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


def _build_archive_fields(
    message,
    sender_id: str,
    user_name: str,
    text_content: str,
    file_tokens: list,
    month_str: str,
    timestamp_ms: int,
) -> dict:
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
        "text": "查看消息",
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


def _update_topic_summary(
    message,
    sender_id: str,
    user_name: str,
    text_content: str,
    root_id: str,
    month_str: str,
    timestamp_ms: int,
):
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
        "text": "查看话题",
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
            "话题链接": topic_link,
        }
        archive_storage.update_or_create_topic(root_id, summary_fields, is_new=True)
    else:
        # 更新已有话题
        old_fields = topic_record["fields"]

        # 更新参与者列表
        participants = set()
        participants_raw = old_fields.get("参与者", "")

        if isinstance(participants_raw, list):
            for item in participants_raw:
                if isinstance(item, dict):
                    name = item.get("text", "")
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
            "话题状态": topic_status,
        }
        archive_storage.update_or_create_topic(root_id, summary_fields, is_new=False)




def do_p2_im_message_reaction_created_v1(data: lark.im.v1.P2ImMessageReactionCreatedV1) -> None:
    """处理表情回复事件（点赞）"""
    from health_monitor import update_event_processed
    
    # 0. 事件去重
    event_id = data.header.event_id
    if event_id in processed_events:
        return
    processed_events.set(event_id, True)  # LRU会自动管理容量，无需手动清理

    event = data.event
    
    # 更新健康监控状态
    update_event_processed("reaction")

    # 获取操作者ID（点赞的人）
    operator_id = event.user_id.open_id if event.user_id else None
    if not operator_id:
        return

    # 获取消息ID
    message_id = event.message_id
    if not message_id:
        return

    # [V3-LOG] 表情回复事件追踪
    now_str = datetime.now().strftime("%H:%M:%S")
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
            user_id=operator_id, user_name=operator_name, metrics_delta={"reaction_given": 1}
        )

        # 4. 更新被点赞者的"被点赞数"
        if message_sender_id != operator_id:  # 避免自己给自己点赞的情况
            storage.update_or_create_record(
                user_id=message_sender_id,
                user_name=receiver_name,
                metrics_delta={"reaction_received": 1},
            )
        else:
            print(f"  > [跳过] 用户给自己点赞")

        print("✅ 表情回复统计成功")

    except Exception as e:
        print(f"❌ 表情回复统计失败: {e}")


# 初始化事件处理器
event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
    .register_p2_im_message_reaction_created_v1(do_p2_im_message_reaction_created_v1)
    .build()
)


def main():
    """
    主函数 - 启动飞书活跃度监控服务
    
    包含以下增强功能：
    1. 环境变量验证
    2. 健康检查HTTP服务
    3. 自动重连机制
    4. Pin监控（可选）
    """
    import time
    from env_validator import validate_environment
    from health_monitor import start_health_monitor, update_websocket_connected, health_monitor
    
    # ========== 1. 环境变量验证 ==========
    try:
        validate_environment()
    except ValueError as e:
        print(f"\n❌ 启动失败：{e}")
        print("\n请检查 .env 文件配置，参考 .env.example 模板")
        return
    
    # ========== 2. 启动健康检查服务 ==========
    health_port = int(os.getenv("HEALTH_CHECK_PORT", 8080))
    try:
        start_health_monitor(port=health_port)
    except Exception as e:
        print(f"⚠️ 健康检查服务启动失败: {e}")
        print("   将继续运行主服务（不影响核心功能）")
    
    # ========== 3. 自动重连循环 ==========
    retry_count = 0
    max_retries = int(os.getenv("MAX_RETRIES", 10))  # 最大重试次数
    retry_delay = int(os.getenv("RETRY_DELAY", 30))  # 重试延迟（秒）
    
    pin_monitor = None
    
    while retry_count < max_retries:
        try:
            # 初始化Pin监控（每次重连都重新初始化）
            pin_table_id = os.getenv("PIN_TABLE_ID")
            pin_interval = int(os.getenv("PIN_MONITOR_INTERVAL", 30))
            
            if pin_table_id and not pin_monitor:
                print(f"🔍 Pin监控已启用 (轮询间隔: {pin_interval}秒)")
                # 注入精华文档归档配置
                essence_doc_token = os.getenv("ESSENCE_DOC_TOKEN")
                pin_monitor = PinMonitor(
                    auth, storage, CHAT_ID, interval=pin_interval,
                    docx_storage=docx_storage, essence_doc_token=essence_doc_token
                )
                pin_monitor.start()
                health_monitor.set_pin_monitor_status(True)
            
            # 启动 Pin 周报调度器 (后台线程,集成到主进程)
            print("\n📅 启动 Pin 周报调度器...")
            try:
                start_pin_scheduler()
            except Exception as e:
                print(f"⚠️  Pin 周报调度器启动失败: {e}")
                print("⚠️  将继续运行,但 Pin 周报功能不可用")
            
            # 初始化长连接客户端
            cli = lark.ws.Client(
                APP_ID, 
                APP_SECRET, 
                event_handler=event_handler, 
                log_level=lark.LogLevel.INFO  # 生产环境使用INFO级别
            )
            
            print("\n" + "=" * 60)
            if retry_count == 0:
                print("🚀 飞书实时监听服务启动")
            else:
                print(f"🔄 正在重新连接 (尝试 {retry_count + 1}/{max_retries})")
            print(f"📅 系统时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"✨ 特性: 环境验证 | 健康检查:{health_port} | 自动重连 | LRU缓存 | API限流")
            print("=" * 60 + "\n")
            
            # 更新健康状态
            update_websocket_connected(True)
            
            # 启动WebSocket客户端（阻塞调用）
            cli.start()
            
            # 如果正常退出（不是异常），重置重试计数
            retry_count = 0
            print("\n✅ WebSocket客户端正常退出")
            
        except KeyboardInterrupt:
            # 用户主动中断
            print("\n\n⚠️ 收到退出信号 (Ctrl+C)")
            print("正在安全关闭服务...")
            update_websocket_connected(False)
            break
            
        except Exception as e:
            # 连接异常，准备重试
            retry_count += 1
            update_websocket_connected(False)
            
            print("\n" + "=" * 60)
            print(f"❌ 连接异常 (尝试 {retry_count}/{max_retries})")
            print(f"   错误信息: {e}")
            print("=" * 60)
            
            if retry_count >= max_retries:
                print(f"\n❌ 已达到最大重试次数 ({max_retries})，程序退出")
                print("   建议检查：")
                print("   1. 网络连接是否正常")
                print("   2. APP_ID和APP_SECRET是否正确")
                print("   3. 飞书应用是否已开通长连接权限")
                break
            
            print(f"⏳ {retry_delay} 秒后自动重连...\n")
            time.sleep(retry_delay)
            
            # 指数退避：每次重试延迟加倍，最多60秒
            retry_delay = min(retry_delay * 2, 60)
        
        finally:
            # 无论如何都确保Pin监控被停止
            if pin_monitor:
                try:
                    # 只在最终退出时停止Pin监控
                    if retry_count >= max_retries or KeyboardInterrupt:
                        print("正在停止Pin监控...")
                        pin_monitor.stop()
                        pin_monitor = None
                        health_monitor.set_pin_monitor_status(False)
                except Exception as e:
                    print(f"⚠️ 停止Pin监控时出错: {e}")
            
            # 停止 Pin 周报调度器
            try:
                print("🚦 正在停止 Pin 周报调度器...")
                stop_pin_scheduler()
            except Exception as e:
                print(f"⚠️  停止 Pin 周报调度器时出错: {e}")
    
    # ========== 4. 清理和退出 ==========
    print("\n" + "=" * 60)
    print("✅ 程序已安全退出")
    print(f"📊 运行统计: 处理了 {health_monitor.status['total_events_processed']} 个事件")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
