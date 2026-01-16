"""
健康检查和监控模块

提供HTTP端点用于检查服务运行状态，支持容器编排和监控系统集成
"""

from flask import Flask, jsonify
import threading
import time
from datetime import datetime
from typing import Dict, Any


class HealthMonitor:
    """健康状态监控器"""
    
    def __init__(self):
        """初始化健康监控器"""
        self.status = {
            "status": "starting",
            "start_time": time.time(),
            "last_event_time": 0,
            "last_heartbeat_time": time.time(),
            "total_events_processed": 0,
            "total_messages_processed": 0,
            "total_reactions_processed": 0,
            "total_errors": 0,
            "websocket_connected": False,
            "pin_monitor_enabled": False,
        }
        self.app = Flask(__name__)
        self._setup_routes()
    
    def _setup_routes(self):
        """设置HTTP路由"""
        
        @self.app.route('/health')
        def health_check():
            """
            健康检查端点
            
            返回服务健康状态
            - 200: 服务健康
            - 503: 服务不健康（超过5分钟未收到事件）
            """
            current_time = time.time()
            uptime_seconds = current_time - self.status["start_time"]
            time_since_last_event = current_time - self.status["last_event_time"]
            
            # 健康判断逻辑
            # 1. 如果刚启动（2分钟内），认为是健康的
            # 2. 如果运行超过2分钟但5分钟内没有收到事件，标记为不健康
            is_just_started = uptime_seconds < 120
            is_receiving_events = time_since_last_event < 300  # 5分钟
            is_healthy = is_just_started or is_receiving_events or self.status["websocket_connected"]
            
            response_data = {
                "status": "healthy" if is_healthy else "unhealthy",
                "uptime_seconds": int(uptime_seconds),
                "uptime_human": self._format_uptime(uptime_seconds),
                "last_event_ago_seconds": int(time_since_last_event) if self.status["last_event_time"] > 0 else None,
                "total_events_processed": self.status["total_events_processed"],
                "total_messages": self.status["total_messages_processed"],
                "total_reactions": self.status["total_reactions_processed"],
                "total_errors": self.status["total_errors"],
                "websocket_connected": self.status["websocket_connected"],
                "pin_monitor_enabled": self.status["pin_monitor_enabled"],
                "timestamp": datetime.now().isoformat(),
            }
            
            status_code = 200 if is_healthy else 503
            return jsonify(response_data), status_code
        
        @self.app.route('/metrics')
        def metrics():
            """
            Prometheus风格的指标端点（可选）
            
            返回可供Prometheus抓取的指标
            """
            metrics_text = f"""# HELP feishu_monitor_uptime_seconds 服务运行时间（秒）
# TYPE feishu_monitor_uptime_seconds gauge
feishu_monitor_uptime_seconds {int(time.time() - self.status["start_time"])}

# HELP feishu_monitor_events_total 处理的事件总数
# TYPE feishu_monitor_events_total counter
feishu_monitor_events_total {self.status["total_events_processed"]}

# HELP feishu_monitor_messages_total 处理的消息总数
# TYPE feishu_monitor_messages_total counter
feishu_monitor_messages_total {self.status["total_messages_processed"]}

# HELP feishu_monitor_reactions_total 处理的表情回复总数
# TYPE feishu_monitor_reactions_total counter
feishu_monitor_reactions_total {self.status["total_reactions_processed"]}

# HELP feishu_monitor_errors_total 错误总数
# TYPE feishu_monitor_errors_total counter
feishu_monitor_errors_total {self.status["total_errors"]}

# HELP feishu_monitor_websocket_connected WebSocket连接状态(1=已连接, 0=未连接)
# TYPE feishu_monitor_websocket_connected gauge
feishu_monitor_websocket_connected {1 if self.status["websocket_connected"] else 0}
"""
            return metrics_text, 200, {'Content-Type': 'text/plain; charset=utf-8'}
        
        @self.app.route('/status')
        def detailed_status():
            """
            详细状态端点
            
            返回所有状态信息（用于调试）
            """
            current_time = time.time()
            uptime_seconds = current_time - self.status["start_time"]
            
            return jsonify({
                **self.status,
                "uptime_seconds": int(uptime_seconds),
                "uptime_human": self._format_uptime(uptime_seconds),
                "current_time": datetime.now().isoformat(),
            })
    
    def _format_uptime(self, seconds: float) -> str:
        """
        格式化运行时间为人类可读格式
        
        Args:
            seconds: 运行秒数
            
        Returns:
            格式化的时间字符串，如 "2天3小时5分钟"
        """
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}天")
        if hours > 0:
            parts.append(f"{hours}小时")
        if minutes > 0:
            parts.append(f"{minutes}分钟")
        
        return "".join(parts) if parts else "不到1分钟"
    
    def update_event(self, event_type: str = "message"):
        """
        更新事件统计
        
        Args:
            event_type: 事件类型，"message"或"reaction"
        """
        self.status["last_event_time"] = time.time()
        self.status["total_events_processed"] += 1
        
        if event_type == "message":
            self.status["total_messages_processed"] += 1
        elif event_type == "reaction":
            self.status["total_reactions_processed"] += 1
    
    def update_error(self):
        """记录错误"""
        self.status["total_errors"] += 1
    
    def update_websocket_status(self, connected: bool):
        """
        更新WebSocket连接状态
        
        Args:
            connected: 是否已连接
        """
        self.status["websocket_connected"] = connected
        if connected:
            self.status["status"] = "running"
        else:
            self.status["status"] = "disconnected"
    
    def set_pin_monitor_status(self, enabled: bool):
        """
        设置Pin监控状态
        
        Args:
            enabled: 是否启用
        """
        self.status["pin_monitor_enabled"] = enabled
    
    def heartbeat(self):
        """
        心跳更新
        
        主循环应定期调用此方法表明服务仍在运行
        """
        self.status["last_heartbeat_time"] = time.time()
    
    def start_server(self, host: str = '0.0.0.0', port: int = 8080):
        """
        启动健康检查HTTP服务器
        
        Args:
            host: 监听地址，默认0.0.0.0（所有接口）
            port: 监听端口，默认8080
        """
        def run():
            # 禁用Flask的日志输出（避免干扰主程序日志）
            import logging
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
            
            self.app.run(host=host, port=port, debug=False, use_reloader=False)
        
        thread = threading.Thread(target=run, daemon=True, name="HealthCheckServer")
        thread.start()
        
        print(f"✅ 健康检查服务已启动")
        print(f"   - 健康检查: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/health")
        print(f"   - 详细状态: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/status")
        print(f"   - Prometheus指标: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/metrics")


# 全局健康监控器实例
health_monitor = HealthMonitor()


# 便捷函数
def start_health_monitor(port: int = 8080):
    """
    启动健康监控服务（便捷函数）
    
    Args:
        port: HTTP端口，默认8080
    """
    health_monitor.start_server(port=port)


def update_event_processed(event_type: str = "message"):
    """
    记录事件处理（便捷函数）
    
    Args:
        event_type: 事件类型
    """
    health_monitor.update_event(event_type)


def update_websocket_connected(connected: bool):
    """
    更新WebSocket连接状态（便捷函数）
    
    Args:
        connected: 是否已连接
    """
    health_monitor.update_websocket_status(connected)


if __name__ == "__main__":
    # 测试健康监控器
    print("启动健康监控测试服务器...")
    start_health_monitor(port=8080)
    
    print("\n测试用例：")
    print("1. 访问 http://localhost:8080/health 查看健康状态")
    print("2. 访问 http://localhost:8080/status 查看详细状态")
    print("3. 访问 http://localhost:8080/metrics 查看Prometheus指标")
    
    # 模拟事件处理
    import time
    for i in range(5):
        time.sleep(2)
        update_event_processed("message")
        print(f"已处理 {i+1} 个事件")
    
    print("\n按 Ctrl+C 退出")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n测试结束")
