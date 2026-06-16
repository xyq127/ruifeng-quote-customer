#!/bin/bash
# 每周一 cron 入口：拉取后端代码 + 扫描接口变更
# 被 crontab 调用，输出到日志文件

BACKEND_DIR="$HOME/web-project/ruifeng-platform/backend-code-repo"
PROJECT_DIR="$HOME/web-project/ruifeng-data-cleaning"
LOG_DIR="$HOME/.claude/cache"
LOG_FILE="$LOG_DIR/backend-scan-$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "==========================================" > "$LOG_FILE"
echo "  后端接口变更检查 - $(date '+%Y-%m-%d %H:%M')" >> "$LOG_FILE"
echo "==========================================" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# 拉取后端代码
cd "$BACKEND_DIR" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "❌ 后端代码目录不存在，尝试克隆..." >> "$LOG_FILE"
  mkdir -p "$(dirname "$BACKEND_DIR")"
  git clone git@gitee.com:rayform_0/backend-code-repo.git "$BACKEND_DIR" >> "$LOG_FILE" 2>&1
  cd "$BACKEND_DIR"
fi

git fetch origin >> "$LOG_FILE" 2>&1
echo "拉取完成" >> "$LOG_FILE"

# 运行扫描脚本
cd "$PROJECT_DIR"
bash scripts/scan-backend.sh >> "$LOG_FILE" 2>&1

echo "" >> "$LOG_FILE"
echo "详情请查看: $LOG_FILE" >> "$LOG_FILE"
