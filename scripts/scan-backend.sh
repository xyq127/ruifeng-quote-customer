#!/bin/bash
# 每周一扫描后端 Controller 变更 — 判断是否需要更新 CLI
# 用法: bash scripts/scan-backend.sh

BACKEND_DIR=~/web-project/ruifeng-platform/backend-code-repo
PROJECT_DIR=$(cd "$(dirname "$0")/.." && pwd)
LAST_SHA_FILE="$PROJECT_DIR/.last-backend-sha"

if [ ! -d "$BACKEND_DIR" ]; then
  echo "❌ 后端代码目录不存在: $BACKEND_DIR"
  echo "请先克隆: git clone git@gitee.com:rayform_0/backend-code-repo.git $BACKEND_DIR"
  exit 1
fi

cd "$BACKEND_DIR"

# 拉取远端最新代码
echo "⟳ 正在拉取后端最新代码..."
git fetch origin 2>/dev/null
if [ $? -ne 0 ]; then
  echo "❌ 拉取失败，请检查网络或 Gitee SSH 配置"
  exit 1
fi

FROM=$(cat "$LAST_SHA_FILE" 2>/dev/null || git rev-parse HEAD~5)
TO=origin/main

echo ""
echo "======================================"
echo "  后端接口变更报告"
echo "======================================"
echo "上次同步: $(git rev-parse --short "$FROM")"
echo "当前远端: $(git rev-parse --short "$TO")"
echo ""

# 检查是否有新的提交
MERGE_BASE=$(git merge-base "$FROM" "$TO")
if [ "$MERGE_BASE" = "$TO" ]; then
  echo "✅ 无新提交，后端代码未变更"
  echo ""
  echo "上次同步的 SHA: $FROM"
  exit 0
fi

# 查找 Controller/接口相关文件的变更
CHANGED=$(git diff "$FROM".."$TO" --name-only | grep -iE 'controller|request/|response/|dto/')
TOTAL_FILES=$(git diff "$FROM".."$TO" --name-only | wc -l)

if [ -z "$CHANGED" ]; then
  echo "✅ 后端有 $TOTAL_FILES 个文件变更，但无 Controller/接口文件变更"
  echo "   CLI 无需更新"
  echo ""
  echo "如需重置同步点，执行:"
  echo "  git -C $BACKEND_DIR rev-parse origin/main > $LAST_SHA_FILE"
  exit 0
fi

echo "⚠️  检测到 Controller/接口文件变更! ($(echo "$CHANGED" | wc -l) 个文件)"
echo ""
echo "📦 变更文件列表:"
echo "$CHANGED" | sed 's/^/  - /'
echo ""
echo "📝 变更统计:"
git diff "$FROM".."$TO" --stat -- $(echo "$CHANGED") 2>/dev/null
echo ""
echo "🔍 变更摘要（前 80 行）:"
git diff "$FROM".."$TO" -- $(echo "$CHANGED") 2>/dev/null | head -80
echo ""
echo "---"
echo "如需更新 CLI，回复 '更新CLI' 开始；如本周跳过，回复 '跳过'"
echo "跳过时不会更新 .last-backend-sha，下周仍会检测相同的变更"
