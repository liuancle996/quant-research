#!/usr/bin/env bash
# A股筛选器 — 一键启动脚本
# 用法: bash screener/run.sh
# 启动后访问 http://localhost:8082

set -euo pipefail

cd "$(dirname "$0")/.."

# 必须取消代理，否则 hikyuu 网络请求失败
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy

echo "📊 启动 A股筛选器..."
echo "   访问地址: http://localhost:8082"
echo "   数据目录: ~/stock/"
echo ""

exec streamlit run screener/app.py \
    --server.port=8082 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.serverAddress=localhost \
    --browser.gatherUsageStats=false \
    --client.toolbarMode=minimal
