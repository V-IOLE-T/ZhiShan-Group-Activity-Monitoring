from collections import defaultdict
import json
import re

class MetricsCalculator:
    def __init__(self, messages, user_names=None):
        self.messages = messages
        self.user_names = user_names or {}
        self.msg_sender_map = {}
    
    def calculate(self):
        metrics = {}
        
        for msg in self.messages:
            msg_id = msg.get('message_id')
            sender = msg.get('sender', {})
            
            # 处理 sender.id 可能是字符串或字典的情况
            sender_id_obj = sender.get('id', {})
            if isinstance(sender_id_obj, dict):
                sender_id = sender_id_obj.get('open_id', '')
            elif isinstance(sender_id_obj, str):
                sender_id = sender_id_obj
            else:
                sender_id = ''
            
            self.msg_sender_map[msg_id] = sender_id
            
            if sender_id and sender_id not in metrics:
                metrics[sender_id] = {
                    'user_id': sender_id,
                    'user_name': self.user_names.get(sender_id, sender_id),
                    'message_count': 0,
                    'char_count': 0,
                    'reply_received': 0,
                    'mention_received': 0,
                    'topic_initiated': 0,
                    'score': 0
                }
        
        for msg in self.messages:
            sender = msg.get('sender', {})
            
            # 处理 sender.id 可能是字符串或字典的情况
            sender_id_obj = sender.get('id', {})
            if isinstance(sender_id_obj, dict):
                sender_id = sender_id_obj.get('open_id', '')
            elif isinstance(sender_id_obj, str):
                sender_id = sender_id_obj
            else:
                sender_id = ''
            
            if not sender_id:
                continue
            
            metrics[sender_id]['message_count'] += 1
            
            content = msg.get('body', {}).get('content', '')
            char_count = self._extract_text_length(content)
            metrics[sender_id]['char_count'] += char_count
            
            parent_id = msg.get('parent_id')
            if parent_id and parent_id in self.msg_sender_map:
                original_sender = self.msg_sender_map[parent_id]
                metrics[original_sender]['reply_received'] += 1
            
            mentions = msg.get('mentions', [])
            for mention in mentions:
                mentioned_id = mention.get('id', {}).get('open_id', '')
                if mentioned_id:
                    metrics[mentioned_id]['mention_received'] += 1
            
            if not msg.get('root_id'):
                msg_id = msg.get('message_id')
                is_topic = any(
                    m.get('root_id') == msg_id 
                    for m in self.messages
                )
                if is_topic:
                    metrics[sender_id]['topic_initiated'] += 1
        
        for user_id, data in metrics.items():
            score = (
                data['message_count'] * 2.0 +
                data['char_count'] * 0.01 +
                data['reply_received'] * 1.5 +
                data['mention_received'] * 1.5 +
                data['topic_initiated'] * 1.5
            )
            metrics[user_id]['score'] = round(score, 2)
        
        return dict(metrics)
    
    def _extract_text_length(self, content):
        try:
            content_obj = json.loads(content)
            text = content_obj.get('text', '')
            text = re.sub(r'@_user_\w+', '', text)
            return len(text.strip())
        except:
            return 0
