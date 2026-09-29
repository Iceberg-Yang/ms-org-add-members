#!/usr/bin/env bash
# ModelScope 组织成员批量添加 —— 一键启动脚本
#
# 用法：
#   ./run.sh                                    交互式引导（默认试运行）
#   ./run.sh <组织名> [站点] [名单文件] [额外参数...]
#
# 示例：
#   ./run.sh MyOrg                              # ai 站、members.txt，试运行
#   ./run.sh MyOrg cn                           # cn 站，试运行
#   ./run.sh MyOrg cn members.txt --apply       # 正式添加
set -euo pipefail
cd "$(dirname "$0")"

SCRIPT="add_members.py"

command -v python3 >/dev/null || { echo "错误：未找到 python3。"; exit 1; }
[ -f "$SCRIPT" ] || { echo "错误：找不到 $SCRIPT（请保持在仓库根目录运行）。"; exit 1; }

if [ "$#" -eq 0 ]; then
  echo "== ModelScope 组织成员批量添加（交互式，默认试运行）=="
  read -r -p "组织名称（组织管理页 URL 中 name= 的值）: " ORG
  [ -n "$ORG" ] || { echo "错误：组织名不能为空。"; exit 1; }
  read -r -p "站点：ai = admin.modelscope.ai（默认）/ cn = admin.modelscope.cn [ai]: " SITE
  SITE="${SITE:-ai}"
  read -r -p "名单文件（每行一个用户名）[members.txt]: " LIST
  LIST="${LIST:-members.txt}"
  if [ ! -f "$LIST" ]; then
    echo "错误：找不到 $LIST（格式参考 members.example.txt）。"
    exit 1
  fi
  python3 "$SCRIPT" "$LIST" --org "$ORG" --site "$SITE"
  echo
  echo "试运行完成。核对输出无误后，正式添加："
  echo "  ./run.sh $ORG $SITE $LIST --apply"
else
  ORG="$1"
  SITE="${2:-ai}"
  LIST="${3:-members.txt}"
  shift $(( $# > 3 ? 3 : $# ))
  python3 "$SCRIPT" "$LIST" --org "$ORG" --site "$SITE" "$@"
fi
