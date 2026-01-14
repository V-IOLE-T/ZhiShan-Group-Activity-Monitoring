from fastapi import FastAPI, Request
import uvicorn
import json
import os
from auth import FeishuAuth
from calculator import MetricsCalculator
from storage import BitableStorage
from collector import MessageCollector
from datetime import datetime

app = FastAPI()

# 初始化组件
auth = FeishuAuth()
storage = BitableStorage(auth)
collector = MessageCollector(auth)
calculator = MetricsCalculator([])

# 用于去重的简单缓存（记录 event_id）
processed_events = set()

# 用户昵称缓存（避免频繁请求通讯录/群成员接口）
user_name_cache = {}

@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        data = await request.json()
    except:
        return {"error": "invalid json"}

    # 1. 飞书 URL 验证请求
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    # 2. 获取事件信息
    header = data.get("header", {})
    event_id = header.get("event_id")
    event_type = header.get("event_type")

    if not event_id:
        return {"status": "no event_id"}

    # 重复事件检查
    if event_id in processed_events:
        return {"status": "already processed"}
    
    processed_events.add(event_id)
    if len(processed_events) > 1000:
        processed_events.clear() # 简单清理

    # 3. 处理接收消息事件
    if event_type == "im.message.receive_v1":
        event_payload = data.get("event", {})
        message = event_payload.get("message", {})
        sender = event_payload.get("sender", {})
        
        sender_id = sender.get("sender_id", {}).get("open_id")
        if not sender_id:
            return {"status": "ignore_no_sender"}

        content_str = message.get("content", "")
        
        # 计算字数
        char_count = calculator._extract_text_length(content_str)
        
        # 确定用户昵称（优先使用缓存，不存在则更新缓存）
        if sender_id not in user_name_cache:
            print(f"正在为用户 {sender_id} 更新昵称缓存...")
            all_names = collector.get_user_names([sender_id])
            user_name_cache.update(all_names)
        
        user_name = user_name_cache.get(sender_id, sender_id)

        # 构建指标增量
        metrics_delta = {
            "message_count": 1,
            "char_count": char_count,
            "reply_received": 0,    # 实时模式下较难统计被回复数（需要历史上下文）
            "mention_received": 0,  # 给被提的人加分逻辑暂未实现
            "topic_initiated": 1 if not message.get("root_id") else 0
        }

        # 更新多维表格
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 实时更新用户: {user_name}")
            storage.update_or_create_record(sender_id, user_name, metrics_delta)
            
            # 如果消息中提到了人，也可以尝试给被提到的人加分（由于飞书只给 open_id，我们需要单独处理）
            mentions = message.get("mentions", [])
            for mention in mentions:
                mentioned_id = mention.get("id", {}).get("open_id")
                if mentioned_id:
                    # 给被@的人加 1.5 分对应的指标
                    storage.update_or_create_record(mentioned_id, mentioned_id, {"mention_received": 1})
            
        except Exception as e:
            print(f"❌ 更新表格失败: {e}")

    return {"status": "ok"}

@app.get("/health")
async def health_check():
    return {"status": "alive"}

if __name__ == "__main__":
    print("🚀 飞书实时监听 Webhook 服务器正在启动...")
    print("💡 请确保您已使用 ngrok 或其他工具将本地 8000 端口暴露到外网")
    print("💡 并在飞书开放平台 -> 事件订阅 -> 请求地址中填入您的外网地址 + /webhook")
    uvicorn.run(app, host="0.0.0.0", port=8000)
