"""
竞品雷达 — 一键启动脚本（Python 版）

启动 Redis → Celery → FastAPI → Vite → 打开浏览器
Ctrl+C 关闭所有服务

用法: python 启动竞品雷达.py
"""

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = r"D:\IT_environment\Miniconda3\envs\ai_agent\python.exe"
REDIS_EXE = r"D:\IT_environment\Redis\redis-server.exe"
NPM_CMD = r"D:\IT_environment\Nvm\nodejs\npm.cmd"
NODE_PATH = r"D:\IT_environment\Nvm\nodejs"

PROCESSES: list[subprocess.Popen] = []


def kill_port(port: int) -> None:
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, encoding="gbk", errors="replace"
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(["taskkill", "/f", "/pid", pid], capture_output=True)
    except Exception:
        pass


def cleanup() -> None:
    print("\n正在关闭所有服务...")
    for p in PROCESSES:
        try:
            p.terminate()
        except Exception:
            pass
    time.sleep(1)
    for p in PROCESSES:
        try:
            p.kill()
        except Exception:
            pass
    kill_port(8000)
    kill_port(5173)
    print("已关闭。")


def _start(cmd: list[str], cwd: str | None = None, env: dict | None = None) -> subprocess.Popen:
    p = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    PROCESSES.append(p)
    return p


def main() -> None:
    os.chdir(ROOT)

    print("=" * 40)
    print("  竞品雷达 启动中...")
    print("=" * 40)

    # [1/4] 清理旧进程
    print("[1/4] 清理旧进程...")
    kill_port(8000)
    kill_port(5173)
    try:
        subprocess.run(["taskkill", "/f", "/im", "redis-server.exe"], capture_output=True)
    except Exception:
        pass

    # [2/4] 启动 Redis
    print("[2/4] 启动 Redis...")
    try:
        subprocess.Popen([REDIS_EXE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    except FileNotFoundError:
        print("  [警告] Redis 未安装在 D:\\IT_environment\\Redis\\，跳过")
        print("  如果本机已有 Redis 在运行，可忽略此警告。")
    time.sleep(2)

    # [3/4] 启动服务
    print("[3/4] 启动服务...")

    if not (ROOT / "frontend" / "node_modules").exists():
        print("  前端依赖未安装，正在 npm install (首次需 1-2 分钟)...")
        subprocess.run([NPM_CMD, "install"], cwd=str(ROOT / "frontend"),
                       check=True, env={**os.environ, "PATH": NODE_PATH + ";" + os.environ.get("PATH", "")})
        print("  npm install 完成")

    env = os.environ.copy()
    env["PATH"] = NODE_PATH + ";" + NODE_PATH + r"\node_modules\.bin;" + env.get("PATH", "")

    _start([PYTHON, "-m", "celery", "-A", "celery_app", "worker",
            "--loglevel=warning", "--pool=solo", "--concurrency=1"])
    print("  Celery   → 已启动")

    _start([PYTHON, "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"])
    print("  FastAPI  → 已启动")

    _start([NPM_CMD, "run", "dev"], cwd=str(ROOT / "frontend"), env=env)
    print("  Vite     → 已启动")

    # [4/4] 等待就绪
    print("[4/4] 等待 FastAPI 就绪...")
    import urllib.request
    for i in range(15):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)
            print(f"  FastAPI 已就绪 ({i + 1}s)")
            break
        except Exception:
            time.sleep(1)
    else:
        print("  [提示] FastAPI 启动较慢，请稍后手动访问 http://localhost:8000/health")

    print()
    print("=" * 40)
    print("  启动完成! http://localhost:5173")
    print("=" * 40)
    print("  Ctrl+C 关闭所有服务")
    print("=" * 40)

    webbrowser.open("http://localhost:5173")

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
