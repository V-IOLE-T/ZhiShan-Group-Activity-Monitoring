import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from auth import FeishuAuth
from storage import BitableStorage

load_dotenv()

# 配置
CARD_TEMPLATE_ID = os.getenv("PIN_REPORT_TEMPLATE_ID", "")  # 卡片模板ID (可选)
CARD_TEMPLATE_VERSION = os.getenv("PIN_REPORT_TEMPLATE_VERSION", "1.0.0")  # 模板版本
PROCESSED_PINS_FILE = Path(__file__).parent / ".processed_pins.txt"  # 已处理Pin记录


def load_processed_pins():
    """加载已处理的Pin消息ID集合"""
    if not PROCESSED_PINS_FILE.exists():
        return set()
    
    try:
        with open(PROCESSED_PINS_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    except Exception as e:
        print(f"⚠️  读取已处理Pin记录失败: {e}")
        return set()


def save_processed_pins(pin_ids):
    """保存已处理的Pin消息ID集合"""
    try:
        with open(PROCESSED_PINS_FILE, 'w', encoding='utf-8') as f:
            for pin_id in sorted(pin_ids):
                f.write(f"{pin_id}\n")
    except Exception as e:
        print(f"⚠️  保存已处理Pin记录失败: {e}")


def main():
    """主函数 - 仅统计和推送本周新增的Pin消息"""
    print(f"{'='*50}")
    print(f"📌 Pin 周报生成器 (仅新增)")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")
    
    auth = FeishuAuth()
    storage = BitableStorage(auth)
    chat_id = os.getenv("CHAT_ID")
    
    if not chat_id:
        print("❌ 错误: 未配置 CHAT_ID")
        return
    
    # 1. 加载已处理的Pin记录
    print("📂 加载已处理Pin记录...")
    processed_pins = load_processed_pins()
    print(f"   已记录: {len(processed_pins)} 条")
    
    # 2. 获取当前所有 Pin 消息
    print("\n📊 正在获取当前 Pin 消息列表...")
    current_pins = get_pinned_messages(auth, chat_id)
    
    if current_pins is None:
        print("❌ 获取 Pin 列表失败")
        return
    
    current_pin_ids = set(pin.get("message_id") for pin in current_pins)
    print(f"   当前 Pin 总数: {len(current_pin_ids)} 条")
    
    # 3. 找出本周新增的Pin (当前有但之前没记录的)
    new_pin_ids = current_pin_ids - processed_pins
    print(f"   本周新增: {len(new_pin_ids)} 条\n")
    
    if len(new_pin_ids) == 0:
        print("💡 本周无新增 Pin 消息")
        send_weekly_report(auth, chat_id, 0, {}, is_empty=True)
        # 更新记录文件 (清理已删除的Pin)
        save_processed_pins(current_pin_ids)
        print(f"\n{'='*50}")
        print("✅ Pin 周报完成 (无新增)")
        print(f"{'='*50}")
        return
    
    # 4. 统计新增Pin的发送者
    print("📈 正在统计新增 Pin 消息发送者...")
    new_pins = [pin for pin in current_pins if pin.get("message_id") in new_pin_ids]
    sender_stats = {}
    
    for i, pin in enumerate(new_pins, 1):
        message_id = pin.get("message_id")
        print(f"  [{i}/{len(new_pins)}] 处理新增消息: {message_id}")
        
        # 获取消息发送者
        sender_info = get_message_sender(auth, message_id)
        if not sender_info:
            print(f"    ⚠️  无法获取发送者信息,跳过")
            continue
        
        sender_id = sender_info.get("sender_id")
        sender_name = sender_info.get("sender_name", sender_id)
        
        if sender_id not in sender_stats:
            sender_stats[sender_id] = {
                "name": sender_name,
                "count": 0
            }
        sender_stats[sender_id]["count"] += 1
        print(f"    ✅ {sender_name}: +1")
    
    print(f"\n📊 本周新增统计: 共 {len(sender_stats)} 位用户被 Pin")
    
    # 5. 更新用户活跃度表 (仅新增的Pin)
    print("\n💾 正在更新用户活跃度表...")
    for sender_id, stats in sender_stats.items():
        try:
            # 一个用户可能在本周新增了多个 Pin
            for _ in range(stats["count"]):
                storage.increment_pin_count(sender_id, stats["name"])
            print(f"  ✅ {stats['name']}: +{stats['count']} 被Pin次数")
        except Exception as e:
            print(f"  ❌ {stats['name']}: 更新失败 - {e}")
    
    # 6. 更新已处理Pin记录
    save_processed_pins(current_pin_ids)
    print(f"\n📝 已更新处理记录 (当前记录 {len(current_pin_ids)} 条)")
    
    # 7. 发送周报卡片到群聊
    print("\n📮 正在发送周报到群聊...")
    send_weekly_report(auth, chat_id, len(new_pin_ids), sender_stats, is_empty=False)
    
    print(f"\n{'='*50}")
    print("✅ Pin 周报完成!")
    print(f"   本周新增: {len(new_pin_ids)} 条")
    print(f"{'='*50}")


def get_pinned_messages(auth, chat_id):
    """获取群内所有 Pin 消息"""
    url = "https://open.feishu.cn/open-apis/im/v1/pins"
    headers = auth.get_headers()
    params = {"chat_id": chat_id}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()
        
        if data.get("code") == 0:
            items = data.get("data", {}).get("items", [])
            return items
        else:
            print(f"❌ API 错误: {data.get('msg')}")
            return None
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return None


def get_message_sender(auth, message_id):
    """获取消息发送者信息"""
    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
    headers = auth.get_headers()
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        if data.get("code") == 0:
            items = data.get("data", {}).get("items", [])
            if items:
                msg = items[0]
                sender = msg.get("sender", {})
                sender_id = sender.get("id", {}).get("open_id")
                
                # 默认使用ID
                sender_name = sender_id
                
                return {
                    "sender_id": sender_id,
                    "sender_name": sender_name
                }
        return None
    except Exception as e:
        print(f"    ❌ 获取消息详情失败: {e}")
        return None


def send_weekly_report(auth, chat_id, new_pin_count, sender_stats, is_empty=False):
    """发送周报卡片到群聊"""
    
    # 生成统计周期
    today = datetime.now()
    week_start = today - timedelta(days=7)
    period = f"{week_start.strftime('%m-%d')} ~ {today.strftime('%m-%d')}"
    
    # 构建排行榜
    if is_empty:
        ranking_text = "本周暂无新增 Pin 消息"
    else:
        ranking = sorted(sender_stats.items(), key=lambda x: x[1]["count"], reverse=True)
        ranking_list = []
        for i, (sender_id, stats) in enumerate(ranking[:10], 1):  # Top 10
            ranking_list.append(f"{i}. {stats['name']}: {stats['count']} 条")
        ranking_text = "\\n".join(ranking_list)
    
    # 判断是否使用模板
    if CARD_TEMPLATE_ID:
        # 使用卡片模板
        card = {
            "type": "template",
            "data": {
                "template_id": CARD_TEMPLATE_ID,
                "template_version_name": CARD_TEMPLATE_VERSION,
                "template_variable": {
                    "new_pins": str(new_pin_count),
                    "period": period,
                    "ranking": ranking_text,
                    "report_date": today.strftime("%Y-%m-%d")
                }
            }
        }
    else:
        # 使用 JSON 卡片
        if is_empty:
            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": "grey",
                    "title": {
                        "tag": "plain_text",
                        "content": f"📌 Pin 消息周报 ({today.strftime('%Y-%m-%d')})"
                    }
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**统计周期**: {period}\\n\\n"
                                       f"💤 本周暂无新增 Pin 消息\\n\\n"
                                       f"_继续保持活跃,期待下周的精华内容!_"
                        }
                    }
                ]
            }
        else:
            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": "orange",
                    "title": {
                        "tag": "plain_text",
                        "content": f"📌 Pin 消息周报 ({today.strftime('%Y-%m-%d')})"
                    }
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**本周新增 Pin 消息**: {new_pin_count} 条\\n\\n"
                                       f"**统计周期**: {period}\\n\\n"
                                       f"**📊 新增被 Pin 排行榜**:\\n{ranking_text}"
                        }
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": "💡 活跃度分数已自动更新 | 每周一早上9:00自动推送"
                            }
                        ]
                    }
                ]
            }
    
    # 发送卡片
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    params = {"receive_id_type": "chat_id"}
    body = {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card)
    }
    
    try:
        response = requests.post(url, headers=auth.get_headers(), params=params, json=body, timeout=10)
        result = response.json()
        
        if result.get("code") == 0:
            print("  ✅ 周报卡片已发送")
        else:
            print(f"  ❌ 发送失败: {result.get('msg')}")
    except Exception as e:
        print(f"  ❌ 发送异常: {e}")


if __name__ == "__main__":
    main()
