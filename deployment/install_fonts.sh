#!/bin/bash
# 在 Linux 云服务器上安装中文字体

echo "开始安装中文字体..."

# 检测操作系统
if [ -f /etc/debian_version ]; then
    # Debian/Ubuntu 系统
    echo "检测到 Debian/Ubuntu 系统"
    sudo apt-get update
    sudo apt-get install -y fonts-wqy-zenhei fonts-wqy-microhei ttf-wqy-zenhei ttf-wqy-microhei
    sudo apt-get install -y fonts-noto-cjk fonts-noto-cjk-extra
    
elif [ -f /etc/redhat-release ]; then
    # CentOS/RHEL 系统
    echo "检测到 CentOS/RHEL 系统"
    sudo yum install -y wqy-zenhei-fonts wqy-microhei-fonts
    sudo yum install -y google-noto-sans-cjk-fonts google-noto-serif-cjk-fonts
    
else
    echo "未知操作系统，请手动安装字体"
    exit 1
fi

# 刷新字体缓存
sudo fc-cache -fv

# 验证字体安装
echo ""
echo "已安装的中文字体："
fc-list :lang=zh | grep -E "WenQuanYi|Noto|Droid"

echo ""
echo "字体安装完成！"
