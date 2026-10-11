# -*- coding: utf-8 -*-
"""
多账号自动连跑脚本 (March7thAssistant) — 命令行入口。

核心逻辑在 tasks/multi_account.py，与 GUI「多账号连跑」开关共用。

用法（在 March7thAssistant 项目根目录运行）:
    # 跑全部已导出的账号（每个账号完整运行: 启动游戏→日常→领奖励→关游戏→切下一个）
    python multi_account_run.py
    # 等价于: python main.py multi

    # 只跑指定账号（UID 即 settings/accounts/ 下的文件名，可在 GUI 账户页看到）
    python multi_account_run.py --accounts 100000001,100000002

    # 每个账号只清体力
    python multi_account_run.py --task power

    # 账号1失败时停止后续账号（默认继续）
    python multi_account_run.py --stop-on-error

前提:
    1. 每个账号都已在 GUI"账户设置"页点过"导出当前游戏账户"
    2. 建议给每个账号配置好"自动登录"（账号密码），防止登录过期卡住
    3. 设置里 after_finish 不要配置为关机/休眠/重启等
"""

import os
import sys
import argparse

# 确保工作目录是项目根目录（settings/accounts 等相对路径依赖它）
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from utils.dpi import configure_dpi_awareness

configure_dpi_awareness()

# 与 main.py 一致：Windows 下请求管理员权限（自动化需要）
if sys.platform == 'win32':
    from utils.admin import is_user_admin, run_as_admin
    if not is_user_admin():
        try:
            run_as_admin()
            sys.exit(0)
        except Exception:
            sys.exit(1)

from module.logger import log
from module.notification import notif
from module.notification.notification import NotificationLevel
from module.localization import load_language

load_language()

from tasks.multi_account import MULTI_TASKS, run


def main():
    parser = argparse.ArgumentParser(description="March7thAssistant 多账号自动连跑")
    parser.add_argument("--accounts", help="要运行的账号UID，逗号分隔，默认跑全部已导出账号")
    parser.add_argument("--task", default="main", choices=list(MULTI_TASKS.keys()),
                        help="每个账号执行的任务，默认 main（完整运行）")
    parser.add_argument("--stop-on-error", action="store_true",
                        help="某个账号失败时停止后续账号（默认失败后继续下一个）")
    args = parser.parse_args()

    account_ids = [x.strip() for x in args.accounts.split(",")] if args.accounts else None
    try:
        ok = run(task=args.task, account_ids=account_ids,
                 stop_on_error=args.stop_on_error, pause_when_done=True)
        sys.exit(0 if ok else 1)
    except KeyboardInterrupt:
        log.error("手动强制停止")
        sys.exit(1)
    except Exception as e:
        log.error(f"发生错误: {e}")
        try:
            notif.notify(content=f"[多账号连跑] 发生错误: {e}",
                         level=NotificationLevel.ERROR)
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
