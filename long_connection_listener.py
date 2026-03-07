import os
import json
import re
import time
import threading
from pathlib import Path
from dotenv import load_dotenv
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from datetime import datetime

# 导入现有模块
from auth import FeishuAuth
from calculator import MetricsCalculator
from storage import BitableStorage, MessageArchiveStorage
from collector import MessageCollector
from config import CACHE_USER_NAME_SIZE, CACHE_EVENT_SIZE
from reply_card import DocCardProcessor
from utils import ThreadSafeLRUCache
from storage import DocxStorage
from message_renderer import MessageToDocxConverter
from pin_scheduler import start_pin_scheduler, stop_pin_scheduler
from services.announcement_service import AnnouncementService

# 加载环境变量 (支持新的 config/ 目录)
env_path = Path(__file__).parent / "config" / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # 向后兼容：如果 config/.env 不存在，尝试根目录
    load_dotenv()

# 初始化配置
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
CHAT_ID = os.getenv("CHAT_ID")
ARCHIVE_DOC_TOKEN = os.getenv("ARCHIVE_DOC_TOKEN")
ANNOUNCEMENT_TAGS = AnnouncementService.parse_tags(os.getenv("ANNOUNCEMENT_TAGS"))
BATCH_FLUSH_INTERVAL_SECONDS = int(os.getenv("BATCH_FLUSH_INTERVAL_SECONDS", "30"))

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

TAG_TRAILING_PUNCTUATION = ".,，。!！?？:：;；、~～)]}】）》\"'“”‘’"


def normalize_hashtag_text(text: str) -> str:
    """将消息中的全角井号统一为半角井号。"""
    return (text or "").replace("＃", "#")


def extract_message_tags(text: str):
    """
    从文本中提取 hashtag。

    Returns:
        raw_tags: 原始提取的标签（不去标点）
        normalized_tags: 归一化后的标签（去末尾标点、去重）
        normalized_text: 归一化文本
    """
    normalized_text = normalize_hashtag_text(text)
    raw_tags = []
    normalized_tags = []

    for match in re.finditer(r"#([^\s#]+)", normalized_text):
        raw_tag = (match.group(1) or "").strip()
        if not raw_tag:
            continue
        raw_tags.append(raw_tag)
        cleaned_tag = raw_tag
        for separator in "。.,，!！?？:：;；、~～":
            if separator in cleaned_tag:
                cleaned_tag = cleaned_tag.split(separator, 1)[0]
        cleaned_tag = cleaned_tag.strip(TAG_TRAILING_PUNCTUATION).strip()
        if cleaned_tag and cleaned_tag not in normalized_tags:
            normalized_tags.append(cleaned_tag)

    return raw_tags, normalized_tags, normalized_text


def _extract_sender_id(sender_obj) -> str:
    """统一提取 sender_id，优先 open_id。"""
    if not sender_obj:
        return ""
    sender_id_obj = getattr(sender_obj, "sender_id", None)
    if not sender_id_obj:
        return ""
    return (
        getattr(sender_id_obj, "open_id", None)
        or getattr(sender_id_obj, "user_id", None)
        or getattr(sender_id_obj, "union_id", None)
        or ""
    )


def _get_event_dedupe_key(header) -> str:
    """构造去重键，避免不同事件类型的 event_id 冲突。"""
    event_type = getattr(header, "event_type", None) or "unknown"
    event_id = getattr(header, "event_id", None) or "unknown"
    return f"{event_type}:{event_id}"

def get_target_doc_token(message):
    """根据消息内容获取目标文档 Token。"""

    route_info = {
        "raw_tags": [],
        "normalized_tags": [],
        "matched": False,
        "matched_tag": None,
        "reason": "",
        "fallback": False,
    }

    # 1. 确定要检查的内容：回复消息优先看根消息标签
    check_content_str = message.content
    is_reply = bool(message.parent_id or message.root_id)
    if is_reply and message.root_id:
        try:
            root_msg = collector.get_message_detail(message.root_id)
            if root_msg:
                check_content_str = root_msg.get("body", {}).get("content", "")
        except Exception as e:
            print(f"  > [路由] 获取根消息失败: {e}")

    # 2. 提取纯文本并解析 hashtag
    plain_text, _ = MetricsCalculator.extract_text_from_content(check_content_str)
    if not plain_text and check_content_str:
        plain_text = str(check_content_str)

    raw_tags, normalized_tags, _ = extract_message_tags(plain_text or "")
    route_info["raw_tags"] = raw_tags
    route_info["normalized_tags"] = normalized_tags

    # 3. 路由规则
    # 无 hashtag：不归档
    if not normalized_tags:
        route_info["reason"] = "no_hashtag"
        return None, "默认", route_info

    # 有 hashtag 且命中 TAG_MAPPING（仅当 token 已配置时归档）
    sorted_tags = sorted(TAG_MAPPING.keys(), key=len, reverse=True)
    for tag in sorted_tags:
        if tag not in normalized_tags:
            continue
        token = TAG_MAPPING.get(tag)
        if token:
            route_info["matched"] = True
            route_info["matched_tag"] = tag
            route_info["reason"] = "matched_tag"
            return token, tag, route_info
        # 标签命中但未配置 token：不归档
        route_info["reason"] = "matched_tag_without_token_no_archive"
        return None, "默认", route_info

    # 有 hashtag 但未命中：不归档
    route_info["reason"] = "unknown_hashtag_no_archive"
    return None, "默认", route_info


# 用户昵称缓存 - 使用线程安全LRU防止内存泄漏
user_name_cache = ThreadSafeLRUCache(capacity=CACHE_USER_NAME_SIZE)

# 事件去重缓存 - 使用线程安全LRU防止内存泄漏
processed_events = ThreadSafeLRUCache(capacity=CACHE_EVENT_SIZE)
# 消息统计快照（用于撤回事件回滚）
message_metric_snapshots = ThreadSafeLRUCache(capacity=CACHE_EVENT_SIZE)
# 已回滚撤回消息缓存（避免重复扣减）
recalled_messages_rolled_back = ThreadSafeLRUCache(capacity=CACHE_EVENT_SIZE)

# 批量更新配置
BATCH_UPDATE_THRESHOLD = 3  # 每 3 条消息更新一次
message_counter = 0
pending_updates = {}  # {user_id: {"user_name": str, "metrics": dict}}
pending_updates_lock = threading.Lock()  # 锁保护多线程访问
last_flush_ts = time.time()
flush_worker_stop_event = threading.Event()
flush_worker_thread = None


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
    """累积用户指标到待更新字典（线程安全）"""
    global pending_updates, pending_updates_lock

    with pending_updates_lock:
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
    """批量更新所有待处理的用户统计（线程安全）"""
    global pending_updates, pending_updates_lock

    with pending_updates_lock:
        if not pending_updates:
            return

        # 复制待更新数据并清空原字典（减少锁持有时间）
        updates_to_process = pending_updates.copy()
        pending_updates = {}

    print(f"📊 批量更新 {len(updates_to_process)} 个用户的统计数据...")

    for user_id, data in updates_to_process.items():
        try:
            storage.update_or_create_record(
                user_id,
                data["user_name"],
                data["metrics"]
            )
        except Exception as e:
            print(f"❌ 更新 {data['user_name']} 失败: {e}")

    print("✅ 批量更新完成")


def maybe_flush_pending_updates(force: bool = False, reason: str = "periodic"):
    """
    根据时间间隔或强制开关触发批量刷新。

    Args:
        force: 是否强制刷新
        reason: 刷新原因（用于日志）
    """
    global message_counter, last_flush_ts

    now = time.time()
    should_flush = force or (now - last_flush_ts >= BATCH_FLUSH_INTERVAL_SECONDS)

    with pending_updates_lock:
        has_pending = bool(pending_updates)

    if not has_pending or not should_flush:
        return

    if force:
        print(f"🧹 触发强制批量刷新 (reason={reason})")
    else:
        print(f"🧹 触发定时批量刷新 (reason={reason})")

    flush_pending_updates()
    message_counter = 0
    last_flush_ts = now


def _flush_worker_loop():
    """后台定时刷新 pending_updates。"""
    while not flush_worker_stop_event.is_set():
        try:
            maybe_flush_pending_updates(force=False, reason="timer")
        except Exception as e:
            print(f"⚠️  定时刷新失败: {e}")
        flush_worker_stop_event.wait(1)


def start_flush_worker():
    """启动后台定时刷新线程。"""
    global flush_worker_thread
    if flush_worker_thread and flush_worker_thread.is_alive():
        return
    flush_worker_stop_event.clear()
    flush_worker_thread = threading.Thread(
        target=_flush_worker_loop,
        daemon=True,
        name="batch-flush-worker",
    )
    flush_worker_thread.start()
    print(f"✅ 批量刷新线程已启动 (interval={BATCH_FLUSH_INTERVAL_SECONDS}s)")


def stop_flush_worker():
    """停止后台定时刷新线程。"""
    flush_worker_stop_event.set()
    if flush_worker_thread and flush_worker_thread.is_alive():
        flush_worker_thread.join(timeout=2)


def _negate_metrics(metrics_delta: dict) -> dict:
    """返回指标增量的反向值。"""
    negated = {}
    for key, value in (metrics_delta or {}).items():
        if isinstance(value, (int, float)) and value:
            negated[key] = -value
    return negated


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
    dedupe_key = _get_event_dedupe_key(data.header)
    if dedupe_key in processed_events:
        print(f"  > [拦截] 该事件已处理过，跳过 (去重)")
        return
    processed_events.set(dedupe_key, True)

    # 获取发送者 OpenID
    sender_id = _extract_sender_id(sender)
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
            # 优先复用已验证稳定的提取逻辑
            message_text, _ = MetricsCalculator.extract_text_from_content(message.content)
            message_text = (message_text or "").strip()

            # 先尝试按文档链接处理（与 1.py 行为一致）
            processed = doc_processor.process_and_reply(message_text, message.chat_id)

            # 兜底：部分消息结构里链接只存在于原始 JSON 文本中
            if not processed and message.content and message.content != message_text:
                processed = doc_processor.process_and_reply(message.content, message.chat_id)

            if processed:
                print(f"  > [单聊] ✅ 文档链接处理成功")
            elif message_text:
                # 纯文本消息，使用白卡样式（不显示标题栏）
                print(f"  > [单聊] 收到纯文本: {message_text[:50]}...")
                try:
                    from reply_card.card_style_generator import CardStyleImageGenerator
                    generator = CardStyleImageGenerator()
                    image_data = generator.generate_card_image("", message_text)
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
    # 路由规则：
    # 1) 命中已知标签且 token 已配置 -> 标签文档
    # 2) 未知标签/无标签/标签异常 -> 不归档文档，但继续统计活跃值
    archive_status_message = "未命中归档规则，不归档文档，但已计入活跃值"
    try:
        target_doc_token, matched_tag, route_info = get_target_doc_token(message)
    except Exception as e:
        target_doc_token = None
        matched_tag = "默认"
        route_info = {
            "raw_tags": [],
            "normalized_tags": [],
            "matched": False,
            "matched_tag": None,
            "reason": "tag_parse_error",
            "fallback": False,
        }
        print(f"  > [路由] 标签解析异常: {e}，默认不归档文档，但继续统计活跃值")

    print(f"  > [路由] 原始标签: {route_info.get('raw_tags') or 'None'}")
    print(f"  > [路由] 归一化标签: {route_info.get('normalized_tags') or 'None'}")
    print(
        f"  > [路由] 匹配结果: {'命中' if route_info.get('matched') else '未命中'}, "
        f"reason={route_info.get('reason')}, fallback={route_info.get('fallback')}"
    )

    if target_doc_token:
        try:
            print(f"  > [归档] 正在采集群消息到文档 {target_doc_token}...")

            sender_nickname = get_cached_nickname(sender_id) if sender_id else "未知用户"

            create_time = message.create_time
            if create_time:
                send_time = datetime.fromtimestamp(int(create_time) / 1000).strftime("%Y-%m-%d %H:%M:%S")
            else:
                send_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            is_reply = bool(message.parent_id or message.root_id)
            print(f"  > [归档] 目标文档: {target_doc_token} (Tag: {matched_tag})")

            # 获取被回复者昵称（仅嵌套回复）
            parent_sender_nickname = None
            if is_reply and message.parent_id and message.root_id and message.parent_id != message.root_id:
                try:
                    parent_msg = collector.get_message_detail(message.parent_id)
                    if parent_msg:
                        parent_sender = parent_msg.get("sender", {})
                        parent_sender_id_obj = parent_sender.get("sender_id", {})
                        parent_uid = (
                            parent_sender_id_obj.get("open_id")
                            or parent_sender_id_obj.get("user_id")
                            or parent_sender_id_obj.get("union_id")
                        )
                        if parent_uid:
                            parent_sender_nickname = get_cached_nickname(parent_uid)
                except Exception as e:
                    print(f"  > [归档] 获取被回复者信息失败: {e}")

            # 仅在匹配到明确标签时移除标签文本；未知标签回退到默认文档时保留原文
            tag_to_remove = matched_tag if route_info.get("matched") else None

            blocks = docx_converter.convert(
                message.content,
                message.message_id,
                target_doc_token,
                sender_name=sender_nickname,
                send_time=send_time,
                is_reply=is_reply,
                parent_sender_name=parent_sender_nickname,
                remove_tag=tag_to_remove,
            )
            docx_storage.add_blocks(target_doc_token, blocks, insert_before_divider=is_reply)
            print(f"  > [归档] ✅ 群消息已同步 (标签: {matched_tag}, Doc: {target_doc_token[-6:]})")
            archive_status_message = "已归档到标签文档，并已计入活跃值"
        except Exception as e:
            print(f"  > [归档] ❌ 同步失败: {e}")
            import traceback
            traceback.print_exc()
            archive_status_message = "标签文档归档失败，但已计入活跃值"
    else:
        print(f"  > [归档] 跳过消息: {route_info.get('reason')}")
        reason = route_info.get("reason")
        if reason == "no_hashtag":
            archive_status_message = "无标签，不归档文档，但已计入活跃值"
        elif reason == "unknown_hashtag_no_archive":
            archive_status_message = "未知标签，不归档文档，但已计入活跃值"
        elif reason == "matched_tag_without_token_no_archive":
            archive_status_message = "标签命中但未配置文档，不归档文档，但已计入活跃值"
        elif reason == "tag_parse_error":
            archive_status_message = "标签解析异常，不归档文档，但已计入活跃值"

    content_str = message.content
    char_count = calculator._extract_text_length(content_str)

    print(f"  > 消息ID: {message.message_id}")
    print(f"  > 父ID (parent_id): {message.parent_id or 'None'}")
    print(f"  > 根ID (root_id): {message.root_id or 'None'}")

    # 3. 获取发送者昵称
    user_name = get_cached_nickname(sender_id)

    # [公告归档] 仅识别公告标签消息并写入 Bitable
    try:
        if AnnouncementService.is_announcement_message(content_str, ANNOUNCEMENT_TAGS):
            if not archive_storage.archive_table_id:
                print("  > [公告归档] ⚠️ 未配置 ARCHIVE_TABLE_ID，跳过公告归档")
            else:
                text_content_for_db, _ = MetricsCalculator.extract_text_from_content(message.content)
                create_time_ms = int(message.create_time) if message.create_time else int(datetime.now().timestamp() * 1000)

                archive_fields = _build_archive_fields(
                    message,
                    user_name,
                    text_content_for_db,
                    create_time_ms,
                )

                if hasattr(archive_storage, "save_message"):
                    saved = archive_storage.save_message(archive_fields)
                    if saved:
                        print("  > [公告归档] ✅ 公告已写入多维表格")
                    else:
                        print("  > [公告归档] ❌ 公告写入失败")
    except Exception as e:
        print(f"  > [公告归档] ❌ 归档失败: {e}")

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
    print(f"  > [归档/统计] {archive_status_message}")

    # 为撤回回滚记录快照（消息发送者基础指标）
    message_snapshot = {
        "message_id": message.message_id,
        "chat_id": message.chat_id,
        "sender_id": sender_id,
        "sender_name": user_name,
        "sender_metrics": dict(metrics_delta),
        "reply_target": None,
        "mention_targets": [],
    }

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
            message_snapshot["reply_target"] = {
                "user_id": target_parent_id,
                "user_name": target_user_name,
            }

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
                message_snapshot["mention_targets"].append(
                    {"user_id": mentioned_id, "user_name": mentioned_name}
                )

    message_metric_snapshots.set(message.message_id, message_snapshot)

    # 8. 检查是否需要批量更新
    message_counter += 1
    if message_counter >= BATCH_UPDATE_THRESHOLD:
        maybe_flush_pending_updates(force=True, reason="threshold")
    else:
        maybe_flush_pending_updates(force=False, reason="receive_event")

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

    # 提取纯文本归档内容和嵌入图片 keys
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
    user_name: str,
    text_content: str,
    timestamp_ms: int,
) -> dict:
    """
    构建消息归档字段

    Args:
        message: 消息对象
        user_name: 发送者姓名
        text_content: 消息文本内容
        timestamp_ms: 时间戳（毫秒）

    Returns:
        归档字段字典
    """
    try:
        send_time_text = datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        send_time_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    archive_fields = {
        "消息ID": message.message_id,
        "话题ID": message.root_id or message.message_id,
        "发送者姓名": user_name,
        "消息内容": text_content,
        "发送时间": send_time_text,
    }

    return archive_fields




def do_p2_im_message_reaction_created_v1(data: lark.im.v1.P2ImMessageReactionCreatedV1) -> None:
    """处理表情回复事件（点赞）"""
    from health_monitor import update_event_processed
    
    # 0. 事件去重
    dedupe_key = _get_event_dedupe_key(data.header)
    if dedupe_key in processed_events:
        return
    processed_events.set(dedupe_key, True)  # LRU会自动管理容量，无需手动清理

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


def do_p2_im_message_reaction_deleted_v1(data: lark.im.v1.P2ImMessageReactionDeletedV1) -> None:
    """处理表情取消事件（回滚点赞统计）。"""
    from health_monitor import update_event_processed

    dedupe_key = _get_event_dedupe_key(data.header)
    if dedupe_key in processed_events:
        return
    processed_events.set(dedupe_key, True)

    event = data.event
    update_event_processed("reaction")

    operator_id = event.user_id.open_id if event.user_id else None
    message_id = event.message_id
    if not operator_id or not message_id:
        return

    now_str = datetime.now().strftime("%H:%M:%S")
    print(f"\n[V3-LOG] [{now_str}] 收到表情取消事件===================")
    print(f"  > 消息ID: {message_id}")
    print(f"  > 操作者ID: {operator_id}")

    try:
        message_sender_id = collector.get_message_sender(message_id)
        if not message_sender_id:
            print("  > [跳过] 无法获取消息发送者，取消点赞回滚终止")
            return

        operator_name = get_cached_nickname(operator_id)
        receiver_name = get_cached_nickname(message_sender_id)

        storage.update_or_create_record(
            user_id=operator_id,
            user_name=operator_name,
            metrics_delta={"reaction_given": -1},
        )

        if message_sender_id != operator_id:
            storage.update_or_create_record(
                user_id=message_sender_id,
                user_name=receiver_name,
                metrics_delta={"reaction_received": -1},
            )
        else:
            print("  > [跳过] 用户取消自己的点赞，不回滚被点赞数")

        print("✅ 表情取消回滚成功")
    except Exception as e:
        print(f"❌ 表情取消回滚失败: {e}")


def do_p2_im_message_recalled_v1(data: lark.im.v1.P2ImMessageRecalledV1) -> None:
    """处理消息撤回事件（回滚活跃度统计）。"""
    from health_monitor import update_event_processed

    dedupe_key = _get_event_dedupe_key(data.header)
    if dedupe_key in processed_events:
        return
    processed_events.set(dedupe_key, True)

    event = data.event
    message_id = event.message_id
    chat_id = event.chat_id

    update_event_processed("message")

    now_str = datetime.now().strftime("%H:%M:%S")
    print(f"\n[V3-LOG] [{now_str}] 收到消息撤回事件===================")
    print(f"  > 消息ID: {message_id}")
    print(f"  > 会话ID: {chat_id}")

    if chat_id and chat_id != CHAT_ID:
        print("  > [跳过] 非目标群撤回事件")
        return

    if not message_id:
        print("  > [跳过] 撤回事件缺少 message_id")
        return

    if message_id in recalled_messages_rolled_back:
        print("  > [跳过] 该消息撤回已回滚过")
        return

    snapshot = message_metric_snapshots.get(message_id)
    if not snapshot:
        print("  > [跳过] 未找到消息快照，无法执行撤回回滚")
        return

    try:
        sender_delta = _negate_metrics(snapshot.get("sender_metrics", {}))
        if sender_delta:
            storage.update_or_create_record(
                user_id=snapshot.get("sender_id"),
                user_name=snapshot.get("sender_name") or get_cached_nickname(snapshot.get("sender_id")),
                metrics_delta=sender_delta,
            )

        reply_target = snapshot.get("reply_target")
        if reply_target and reply_target.get("user_id"):
            storage.update_or_create_record(
                user_id=reply_target["user_id"],
                user_name=reply_target.get("user_name") or get_cached_nickname(reply_target["user_id"]),
                metrics_delta={"reply_received": -1},
            )

        for mention_target in snapshot.get("mention_targets", []):
            user_id = mention_target.get("user_id")
            if not user_id:
                continue
            storage.update_or_create_record(
                user_id=user_id,
                user_name=mention_target.get("user_name") or get_cached_nickname(user_id),
                metrics_delta={"mention_received": -1},
            )

        recalled_messages_rolled_back.set(message_id, True)
        print("✅ 消息撤回回滚成功")
    except Exception as e:
        print(f"❌ 消息撤回回滚失败: {e}")


def do_p2_im_chat_access_event_bot_p2p_chat_entered_v1(data) -> None:
    """忽略机器人进入单聊事件，避免 WS 层报 processor not found。"""
    return


def do_p2_customized_event_p2p_chat_create(data) -> None:
    """忽略 p2p_chat_create 事件，避免 WS 层报 processor not found。"""
    dedupe_key = _get_event_dedupe_key(data.header)
    if dedupe_key in processed_events:
        return
    processed_events.set(dedupe_key, True)
    print("  > [事件] 已忽略 p2p_chat_create")


# 初始化事件处理器
event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
    .register_p2_im_message_reaction_created_v1(do_p2_im_message_reaction_created_v1)
    .register_p2_im_message_reaction_deleted_v1(do_p2_im_message_reaction_deleted_v1)
    .register_p2_im_message_recalled_v1(do_p2_im_message_recalled_v1)
    .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(do_p2_im_chat_access_event_bot_p2p_chat_entered_v1)
    .register_p2_customized_event("p2p_chat_create", do_p2_customized_event_p2p_chat_create)
    .build()
)


def main():
    """
    主函数 - 启动飞书活跃度监控服务
    
    包含以下增强功能：
    1. 环境变量验证
    2. 健康检查HTTP服务
    3. 自动重连机制
    4. 每周 Pin 审计 + 月度归档调度
    """
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

    # 启动批量写入兜底线程
    try:
        start_flush_worker()
    except Exception as e:
        print(f"⚠️  批量刷新线程启动失败: {e}")
        print("   将继续运行主服务（仍可依赖阈值刷新）")
    
    # ========== 3. 自动重连循环 ==========
    retry_count = 0
    max_retries = int(os.getenv("MAX_RETRIES", 10))  # 最大重试次数
    retry_delay = int(os.getenv("RETRY_DELAY", 30))  # 重试延迟（秒）
    
    while retry_count < max_retries:
        try:
            # 不启用秒级 Pin 轮询，状态置为 false
            health_monitor.set_pin_monitor_status(False)

            # 启动 每周 Pin 审计 & 月度归档调度器 (后台线程,集成到主进程)
            print("\n📅 启动 每周 Pin 审计 & 月度归档调度器...")
            try:
                start_pin_scheduler(auth)
            except Exception as e:
                print(f"⚠️  调度器启动失败: {e}")
                print("⚠️  将继续运行,但 每周 Pin 审计和月度归档功能不可用")
            
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
            maybe_flush_pending_updates(force=True, reason="keyboard_interrupt")
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
            # 退出/重连前强制 flush，避免未达阈值导致的数据丢失
            maybe_flush_pending_updates(force=True, reason="ws_loop_finally")
            # 停止每周 Pin 审计 & 月度归档调度器
            try:
                print("🚦 正在停止 每周 Pin 审计调度器...")
                stop_pin_scheduler()
            except Exception as e:
                print(f"⚠️  停止调度器时出错: {e}")
    
    # ========== 4. 清理和退出 ==========
    stop_flush_worker()
    maybe_flush_pending_updates(force=True, reason="process_exit")
    print("\n" + "=" * 60)
    print("✅ 程序已安全退出")
    print(f"📊 运行统计: 处理了 {health_monitor.status['total_events_processed']} 个事件")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
