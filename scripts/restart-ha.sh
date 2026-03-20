#!/bin/bash
# 文件位置: /home/zhongsheng/PycharmProjects/Datamind/scripts/restart-ha.sh

# 重启高可用环境
echo "重启 Datamind 高可用环境..."

./scripts/stop-ha.sh
sleep 3
./scripts/deploy-ha.sh

echo "服务已重启"