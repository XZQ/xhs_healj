#!/usr/bin/env bash
# 一键启动 xhs_healj 开发环境：后端 (uvicorn --reload) + 前端 (vite)
#
# 用法（项目根目录或任意目录均可）：
#   bash scripts/dev.sh            # 同时起前后端（默认）
#   bash scripts/dev.sh backend    # 仅后端
#   bash scripts/dev.sh frontend   # 仅前端
#
# 首次运行会自动创建 .venv 并安装依赖；之后幂等跳过。
# 修改 pyproject.toml 后会自动重装后端依赖。
# Ctrl-C 退出时自动回收前端子进程。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:-all}"
case "$MODE" in
  all|backend|frontend) ;;
  *)
    echo "未知参数: ${MODE}（可选: all | backend | frontend）" >&2
    exit 2
    ;;
esac

VENV="$ROOT/.venv"
PY="$VENV/bin/python"
STAMP="$VENV/.deps_installed"

# ---------- 后端环境 ----------
setup_backend() {
  if [ ! -x "$PY" ]; then
    echo ">> 创建虚拟环境 .venv"
    python3 -m venv "$VENV"
  fi
  # shellcheck disable=SC1091
  . "$VENV/bin/activate"
  python -m pip install -U pip >/dev/null

  # pyproject.toml 变更后自动重装；否则幂等跳过
  if [ ! -f "$STAMP" ] || [ pyproject.toml -nt "$STAMP" ]; then
    echo ">> 安装后端依赖 (pip install -e .[dev])"
    python -m pip install -e ".[dev]"
    touch "$STAMP"
  fi
}

# ---------- 前端环境 ----------
setup_frontend() {
  if [ ! -f frontend/package.json ]; then
    echo "!! 未找到 frontend/package.json，跳过前端" >&2
    return 1
  fi
  if [ ! -d frontend/node_modules ]; then
    echo ">> 安装前端依赖 (npm install)"
    (cd frontend && npm install)
  fi
}

# ---------- 加载本地 .env ----------
load_env() {
  if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
    echo ">> 已加载 .env"
  fi
}

# ---------- 启动 ----------
FRONTEND_PID=""
cleanup() {
  if [ -n "$FRONTEND_PID" ]; then
    echo
    echo ">> 停止前端进程 $FRONTEND_PID"
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [ "$MODE" = "all" ] || [ "$MODE" = "frontend" ]; then
  if setup_frontend; then
    echo ">> 启动前端 http://127.0.0.1:5173"
    (cd frontend && npm run dev) &
    FRONTEND_PID=$!
  fi
fi

if [ "$MODE" = "all" ] || [ "$MODE" = "backend" ]; then
  setup_backend
  load_env
  echo ">> 启动后端 http://127.0.0.1:8000  (Ctrl-C 退出)"
  echo ">> Health: http://127.0.0.1:8000/api/v1/health"
  # 前台运行后端；退出时上面的 trap 会带走前端
  exec python -m uvicorn xhs_health.main:app --reload
fi

# 仅前端模式：前台等待前端进程
wait "$FRONTEND_PID"
