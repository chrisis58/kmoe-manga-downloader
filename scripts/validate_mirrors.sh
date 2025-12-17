#!/bin/bash

# ================= CONFIGURATION =================
MIRROS_URL="https://cdn.jsdelivr.net/gh/chrisis58/kmoe-manga-downloader@main/mirror/mirrors.json"
API_ROUTE_LOGIN="/login.php"
TIMEOUT=5
REPORT_FILE="failed_report.md"
# =================================================

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

rm -f "$REPORT_FILE"

if ! command -v jq &> /dev/null; then
    echo -e "${RED}错误: 未找到 jq 命令。${NC}"
    exit 1
fi

echo "正在从远程获取配置..."
echo "源地址: $MIRROS_URL"

json_content=$(curl -sL --fail "$MIRROS_URL")

if [ $? -ne 0 ] || [ -z "$json_content" ]; then
    echo -e "${RED}错误: 无法下载配置文件或文件为空！${NC}"
    exit 1
fi

echo "获取成功，开始探测镜像地址..."
echo "----------------------------------------"

urls=$(echo "$json_content" | jq -r '([.default] + .alternatives) | flatten | map(select(. != null)) | .[]')

IFS=$'\n'

for base_url in $urls; do
    if [ -z "$base_url" ]; then continue; fi
    
    clean_base="${base_url%/}"
    target_url="${clean_base}${API_ROUTE_LOGIN}"

    response=$(curl -I -s -D - -m "$TIMEOUT" -o /dev/null "$target_url" 2>&1)
    curl_exit_code=$?

    if [ $curl_exit_code -ne 0 ]; then
        echo -e "${YELLOW}连接失败: ${base_url} (Curl Error: $curl_exit_code)${NC}"
        echo "- ❌ **连接失败**: ${base_url} (Curl exit code: $curl_exit_code)" >> "$REPORT_FILE"
        continue
    fi

    status_code=$(echo "$response" | head -n 1 | awk '{print $2}')

    if [ "$status_code" == "200" ]; then
        echo -e "${GREEN}[有效] $base_url (200 OK)${NC}"
    
    elif [[ "$status_code" =~ ^(301|302|307|308)$ ]]; then
        location=$(echo "$response" | grep -i "^Location:" | awk '{print $2}' | tr -d '\r')
        new_base=$(echo "$location" | awk -F/ '{OFS="/"; print $1,$2,$3}')
        echo -e "${YELLOW}重定向 ($status_code): $base_url -> ${new_base}${NC}"
        echo "- ⚠️ **发生重定向**: ${base_url} -> ${new_base}" >> "$REPORT_FILE"
    else
        echo -e "${RED}[无效] $base_url (状态码: $status_code)${NC}"
        echo "- 🚫 **HTTP 异常**: ${base_url} (Status: $status_code)" >> "$REPORT_FILE"
    fi

done

unset IFS

if [ -s "$REPORT_FILE" ]; then
    echo "----------------------------------------"
    echo -e "${RED}发现异常链接，已生成报告: $REPORT_FILE${NC}"
else
    echo "----------------------------------------"
    echo -e "${GREEN}所有链接探测正常。${NC}"
fi