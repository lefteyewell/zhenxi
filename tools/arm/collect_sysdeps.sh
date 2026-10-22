#!/bin/bash
# 麒麟真机离线系统库收集：容器内执行，产出 kylin-sysdeps-aarch64.tar.gz
# 用法: docker run --rm --platform linux/arm64 -v 项目:/app -w /app photo-build-arm64:stage5 bash tools/arm/collect_sysdeps.sh
set -e
apt-get update -qq
PACKAGES="libgl1 libglib2.0-0 libxcb1 libxcb-cursor0 libxkbcommon-x11-0 fonts-noto-cjk"
rm -rf /tmp/sysdeps && mkdir -p /tmp/sysdeps
cd /tmp/sysdeps
# 递归收集依赖列表（apt-get download 不检查安装状态，可直接取回已安装包）
DEPS=$(apt-cache depends --recurse --no-recommends --no-suggests --no-conflicts --no-breaks \
       $PACKAGES 2>/dev/null | grep '^\w' | sort -u | grep -v '^libc6$' || true)
echo "target packages: $(echo $PACKAGES $DEPS | tr ' ' '\n' | sort -u | wc -l)"
apt-get download $PACKAGES $DEPS 2>&1 | grep -v "^Get:" || true
echo "collected: $(ls *.deb 2>/dev/null | wc -l)"
tar czf /app/dist_arm/kylin-sysdeps-aarch64.tar.gz *.deb
ls -lh /app/dist_arm/kylin-sysdeps-aarch64.tar.gz
