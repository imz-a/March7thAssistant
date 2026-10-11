# -*- coding: utf-8 -*-
"""
多账号自动连跑脚本 (March7thAssistant)

用法（在 March7thAssistant 项目根目录、命令行运行）:
    python main.py 之外，请勿通过图形界面启动本脚本。

    # 跑全部已导出的账号（每个账号完整运行: 启动游戏→日常→领奖励→关游戏→切下一个）
    python multi_account_run.py

    # 只跑指定账号（UID 即 settings/accounts/ 下的文件名，可在 GUI 账户页看到）
    python multi_account_run.py --accounts 100000001,100000002

    # 账号1失败时是否继续跑账号2（默认继续）
    python multi_account_run.py --stop-on-error

前提:
    1. 每个账号都已在 GUI"账户设置"页点过"导出当前游戏账户"
    2. 建议给每个账号配置好"自动登录"（账号密码），防止登录过期卡住
    3. 设置里 after_finish 不要配置为关机/休眠/重启等
"""

import os
import sys
import time
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

from module.config import cfg
from module.logger import log
from module.notification import notif
from module.notification.notification import NotificationLevel
from module.localization import load_language

load_language()

from app.tools import account_manager
from app.tools.account_manager import load_to_account
import tasks.game as game
import tasks.reward as reward
import tasks.version as version
from module.game import get_game_controller
from tasks.daily.daily import Daily
from tasks.daily.fight import Fight
from tasks.power.power import Power
from module.ocr import ocr
from utils.console import pause_on_success


TASKS = {
    "main": "完整运行（日常实训+领奖励）",
    "daily": "每日实训 + 领奖励",
    "power": "清体力",
    "routine": "每日实训",
    "fight": "锄大地",
}


def run_tasks_once(task: str):
    """对当前已登录账号执行一遍任务（不调用 game.stop，避免触发退出/循环逻辑）"""
    if task == "main":
        version.start()
        game.start()
        Daily.start()
        reward.start()
    elif task == "daily":
        game.start()
        Daily.run()
        reward.start()
    elif task == "power":
        game.start()
        Power.run()
    elif task == "routine":
        game.start()
        Daily.routine()
    elif task == "fight":
        game.start()
        Fight.start()
    else:
        raise ValueError(f"未知任务: {task}")

    # 关闭游戏进程，为切换下一个账号做准备
    get_game_controller().stop_game()


def notify(content: str, level: NotificationLevel = NotificationLevel.ALL):
    try:
        notif.notify(content=content, level=level)
    except Exception as e:
        log.warning(f"发送通知失败: {e}")


def resolve_targets(accounts_arg: str | None):
    account_manager.reload_all_account_from_files()
    all_accounts = account_manager.accounts
    if not all_accounts:
        log.error("settings/accounts 下没有任何已导出的账号。请先在 GUI 账户页对每个账号执行'导出当前游戏账户'。")
        sys.exit(1)

    if accounts_arg:
        wanted = {int(x.strip()) for x in accounts_arg.split(",") if x.strip()}
        found = {a.account_id: a for a in all_accounts}
        missing = wanted - set(found.keys())
        if missing:
            log.error(f"以下账号未导出过，无法使用: {missing}。已导出账号: {list(found.keys())}")
            sys.exit(1)
        ordered = [found[uid] for uid in wanted]
    else:
        ordered = list(all_accounts)
    return ordered


def main():
    parser = argparse.ArgumentParser(description="March7thAssistant 多账号自动连跑")
    parser.add_argument("--accounts", help="要运行的账号UID，逗号分隔，默认跑全部已导出账号")
    parser.add_argument("--task", default="main", choices=list(TASKS.keys()),
                        help="每个账号执行的任务，默认 main（完整运行）")
    parser.add_argument("--stop-on-error", action="store_true",
                        help="某个账号失败时停止后续账号（默认失败后继续下一个）")
    args = parser.parse_args()

    log.hr(f"多账号连跑开始，任务: {TASKS[args.task]}", 0)

    targets = resolve_targets(args.accounts)
    log.info("本次将依次运行以下账号: " + ", ".join(f"{a.account_name}({a.account_id})" for a in targets))

    results = []  # (账号, 是否成功, 耗时秒)
    for index, account in enumerate(targets, start=1):
        log.hr(f"[{index}/{len(targets)}] 切换到账号: {account.account_name}({account.account_id})", 1)
        start_time = time.time()
        success = True
        try:
            # 确保游戏未运行（切换注册表必须在游戏关闭状态下进行）
            get_game_controller().stop_game()
            # 切换账号（若已是该账号则无需重载）
            load_to_account(account.account_id)
            log.info(f"账号已切换: {account.account_name}({account.account_id})")
            # 运行前重新加载配置
            cfg._load_config()
            run_tasks_once(args.task)
        except Exception as e:
            success = False
            log.error(f"账号 {account.account_name}({account.account_id}) 运行失败: {e}")
            # 确保游戏被关闭再继续下一个
            try:
                get_game_controller().stop_game()
            except Exception:
                pass
            notify(f"[多账号连跑] 账号 {account.account_name}({account.account_id}) 运行失败: {e}",
                   NotificationLevel.ERROR)
            if args.stop_on_error:
                log.error("已启用 --stop-on-error，停止后续账号")
                results.append((account, False, time.time() - start_time))
                break

        cost = time.time() - start_time
        results.append((account, success, cost))
        log.info(f"账号 {account.account_name}({account.account_id}) "
                 f"{'完成' if success else '失败'}，耗时 {cost / 60:.1f} 分钟")
        # 释放 OCR 内存（与 game.stop 行为一致）
        ocr.exit_ocr()
        if cfg.notify_merge:
            notif.flush_batch()

    # 汇总通知
    lines = [f"{a.account_name}({a.account_id}): {'✅ 成功' if ok else '❌ 失败'} ({c / 60:.1f} 分钟)"
             for a, ok, c in results]
    summary = "[多账号连跑] 运行完毕\n" + "\n".join(lines)
    log.hr("运行汇总", 1)
    for line in lines:
        log.info(line)
    notify(summary)
    log.hr("多账号连跑结束", 0)
    pause_on_success()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.error("手动强制停止")
        sys.exit(1)
    except Exception as e:
        log.error(f"发生错误: {e}")
        notify(f"[多账号连跑] 发生错误: {e}", NotificationLevel.ERROR)
        pause_on_success()
        sys.exit(1)
