# 云服务器部署完整指南 - 修复字体问题

## 问题根源

代码原本使用的字体（微软雅黑、黑体）是 Windows 字体，在 Linux 云服务器上不存在，导致中文内容无法正确显示在生成的图片中。

## 解决方案

已修改代码以支持 Linux 常见中文字体。现在需要在云服务器上安装中文字体。

---

## 部署步骤

### 1️⃣ 安装中文字体

在云服务器上执行以下命令：

#### Debian/Ubuntu 系统：
```bash
# 更新包列表
sudo apt-get update

# 安装文泉驿字体（推荐）
sudo apt-get install -y fonts-wqy-zenhei fonts-wqy-microhei

# 或安装 Noto CJK 字体（可选，更全面）
sudo apt-get install -y fonts-noto-cjk fonts-noto-cjk-extra

# 刷新字体缓存
sudo fc-cache -fv
```

#### CentOS/RHEL 系统：
```bash
# 安装文泉驿字体
sudo yum install -y wqy-zenhei-fonts wqy-microhei-fonts

# 或安装 Noto CJK 字体
sudo yum install -y google-noto-sans-cjk-fonts

# 刷新字体缓存
sudo fc-cache -fv
```

### 2️⃣ 验证字体安装

```bash
# 查看已安装的中文字体
fc-list :lang=zh

# 应该能看到 WenQuanYi 或 Noto 相关的字体
fc-list :lang=zh | grep -E "WenQuanYi|Noto"
```

### 3️⃣ 更新代码

```bash
cd /www/wwwroot/feishu_zhishan_bot

# 拉取最新代码（包含跨平台字体支持）
git pull

# 或者重新上传修改后的文件：
# - reply_card/card_style_generator.py
```

### 4️⃣ 重启应用

```bash
# 停止旧进程
pkill -f long_connection_listener.py

# 启动新进程
python3 long_connection_listener.py
```

### 5️⃣ 测试

- 发送文档链接给机器人
- 查看日志，应该能看到：
  ```
  ✅ 成功加载字体: /usr/share/fonts/truetype/wqy/wqy-zenhei.ttc (大小: 32)
  ```

---

## 使用安装脚本（快捷方式）

我已经创建了自动安装脚本 `install_fonts.sh`，可以一键安装：

```bash
# 上传 install_fonts.sh 到服务器

# 添加执行权限
chmod +x install_fonts.sh

# 运行脚本
./install_fonts.sh
```

---

## 故障排查

### 问题1：看到警告"未找到可用的中文字体"

**原因**：字体未正确安装

**解决**：
1. 确认字体已安装：`fc-list :lang=zh`
2. 如果列表为空，重新安装字体
3. 刷新字体缓存：`sudo fc-cache -fv`

### 问题2：图片仍然显示空白

**可能原因**：
1. MCP API 调用失败（查看日志中的 MCP 调用部分）
2. 图片生成失败（查看是否有 Python 错误）
3. Pillow 库版本问题

**检查方法**：
```bash
# 查看完整日志
tail -f /path/to/log/file

# 测试 Pillow 是否正常
python3 -c "from PIL import Image, ImageDraw, ImageFont; print('Pillow 正常')"

# 测试 pilmoji 是否正常
python3 -c "from pilmoji import Pilmoji; print('pilmoji 正常')"
```

### 问题3：字体路径不匹配

不同 Linux 发行版的字体路径可能不同。如果默认路径不起作用，手动查找字体：

```bash
# 查找 WenQuanYi 字体的实际路径
find /usr -name "*wqy*.ttc" 2>/dev/null

# 查找 Noto 字体的实际路径
find /usr -name "*Noto*CJK*.ttc" 2>/dev/null
```

如果路径不同，可以手动修改 `card_style_generator.py` 中的字体路径。

---

## 代码改进说明

已修改的文件：`reply_card/card_style_generator.py`

**主要改动**：
1. 添加了 Linux 常见中文字体路径（文泉驿、Noto CJK）
2. 保留了 Windows 字体支持（兼容本地开发环境）
3. 添加了字体加载成功的日志
4. 添加了字体加载失败的警告

**兼容性**：
- ✅ Windows（本地开发）
- ✅ Linux（云服务器）
- ✅ 自动降级（如果找不到中文字体，使用默认字体）

---

## 推荐字体

按优先级排序：

1. **文泉驿正黑** (WenQuanYi Zen Hei)
   - 优点：轻量、显示效果好、Linux 常见
   - 安装：`sudo apt-get install fonts-wqy-zenhei`

2. **Noto Sans CJK**
   - 优点：Google 开发、支持多种语言、高质量
   - 安装：`sudo apt-get install fonts-noto-cjk`

3. **文泉驿微米黑** (WenQuanYi Micro Hei)
   - 优点：更细、更现代
   - 安装：`sudo apt-get install fonts-wqy-microhei`

---

## 下一步

1. ✅ 安装中文字体
2. ✅ 更新代码
3. ✅ 重启应用
4. ✅ 测试并查看日志
5. ✅ 确认卡片图片显示正常

如果问题仍然存在，请提供：
- 完整的应用日志
- `fc-list :lang=zh` 的输出
- Python 版本和 Pillow 版本
