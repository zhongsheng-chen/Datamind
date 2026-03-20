#!/bin/bash
# 文件位置: /home/zhongsheng/PycharmProjects/Datamind/scripts/stop-ha.sh

# 停止高可用环境
echo "停止 Datamind 高可用环境..."

docker-compose down

echo "服务已停止"