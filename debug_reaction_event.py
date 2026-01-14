"""
调试表情回复事件结构
"""
import os
from dotenv import load_dotenv
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from datetime import datetime

load_dotenv()

APP_ID = os.getenv('APP_ID')
APP_SECRET = os.getenv('APP_SECRET')

def do_p2_im_message_reaction_created_v1(data: lark.im.v1.P2ImMessageReactionCreatedV1) -> None:
    """调试表情回复事件"""
    print("\n" + "="*60)
    print("收到表情回复事件")
    print("="*60)
    
    # 打印整个事件对象的属性
    print(f"\n[DEBUG] data 类型: {type(data)}")
    print(f"[DEBUG] data.event 类型: {type(data.event)}")
    
    event = data.event
    
    # 尝试打印所有可能的属性
    print(f"\n[DEBUG] event 对象的所有属性:")
    for attr in dir(event):
        if not attr.startswith('_'):
            try:
                value = getattr(event, attr)
                if not callable(value):
                    print(f"  - {attr}: {value}")
            except Exception as e:
                print(f"  - {attr}: <无法访问: {e}>")
    
    # 尝试访问 user_id
    print(f"\n[DEBUG] 尝试访问 user_id:")
    try:
        user_id_obj = event.user_id
        print(f"  user_id 对象: {user_id_obj}")
        print(f"  user_id 类型: {type(user_id_obj)}")
        
        if user_id_obj:
            print(f"  user_id 的属性:")
            for attr in dir(user_id_obj):
                if not attr.startswith('_'):
                    try:
                        value = getattr(user_id_obj, attr)
                        if not callable(value):
                            print(f"    - {attr}: {value}")
                    except:
                        pass
    except Exception as e:
        print(f"  错误: {e}")
    
    print("\n" + "="*60)

# 初始化事件处理器
event_handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_reaction_created_v1(do_p2_im_message_reaction_created_v1) \
    .build()

def main():
    if not APP_ID or not APP_SECRET:
        print("❌ 错误: 请在 .env 中配置 APP_ID 和 APP_SECRET")
        return

    cli = lark.ws.Client(
        APP_ID, 
        APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO
    )

    print("="*60)
    print("🔍 表情回复事件调试工具")
    print("="*60)
    print("请在群里给任意消息添加表情回复...")
    print("程序将打印事件对象的详细信息")
    print("="*60)

    cli.start()

if __name__ == "__main__":
    main()
