# -*- coding: utf-8 -*-
"""多账号自动连跑。

依次切换到每个已导出的账号并运行任务（完整运行/清体力/锄大地等），
全部完成后发送汇总通知。GUI 的「多账号连跑」开关与命令行
`python main.py multi` / `multi_account_run.py` 共用本模块。
"""
import time

from module.config import cfg
from module.logger import log
from module.notification import notif
from module.notification.notification import NotificationLevel
from module.game import get_game_controller
from module.ocr import ocr
from app.tools import account_manager
from app.tools.account_manager import load_to_account
import tasks.game as game
import tasks.reward as reward
import tasks.version as version
from tasks.daily.daily import Daily
from tasks.daily.fight import Fight
from tasks.power.power import Power

# 任务名 -> 说明（msgid，显示时自行调用 tr()）
MULTI_TASKS = {
    "main": "完整运行（日常实训+领奖励）",
    "daily": "每日实训 + 领奖励",
    "power": "清体力",
    "routine": "每日实训",
    "fight": "锄大地",
}


def _notify(content: str, level=NotificationLevel.ALL):
    try:
        notif.notify(content=content, level=level)
    except Exception as e:
        log.warning(f"发送通知失败: {e}")


def _run_tasks_once(task: str):
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


def resolve_targets(account_ids=None):
    """解析要运行的账号列表（默认全部已导出账号）"""
    account_manager.reload_all_account_from_files()
    all_accounts = account_manager.accounts
    if not all_accounts:
        raise RuntimeError(
            "settings/accounts 下没有任何已导出的账号。"
            "请先在 GUI 账户页对每个账号执行'导出当前游戏账户'。")

    if account_ids:
        found = {a.account_id: a for a in all_accounts}
        # 按用户给定顺序去重，保证运行顺序可预期
        wanted = list(dict.fromkeys(int(x) for x in account_ids))
        missing = set(wanted) - set(found.keys())
        if missing:
            raise RuntimeError(
                f"以下账号未导出过，无法使用: {sorted(missing)}。"
                f"已导出账号: {sorted(found.keys())}")
        return [found[uid] for uid in wanted]
    return list(all_accounts)


def run(task: str = "main", account_ids=None, stop_on_error: bool = False,
        pause_when_done: bool = False):
    """依次运行所有目标账号，结束后发送汇总通知。"""
    from utils.console import pause_on_success

    if task not in MULTI_TASKS:
        raise ValueError(f"未知任务: {task}")

    log.hr(f"多账号连跑开始，任务: {MULTI_TASKS[task]}", 0)

    targets = resolve_targets(account_ids)
    log.info("本次将依次运行以下账号: " +
             ", ".join(f"{a.account_name}({a.account_id})" for a in targets))

    results = []  # (账号, 是否成功, 耗时秒)
    for index, account in enumerate(targets, start=1):
        log.hr(f"[{index}/{len(targets)}] 切换到账号: "
               f"{account.account_name}({account.account_id})", 1)
        start_time = time.time()
        success = True
        try:
            # 确保游戏未运行（切换注册表必须在游戏关闭状态下进行）
            get_game_controller().stop_game()
            # 切换账号（若已是该账号则无需重载；配置跟随账号开启时会同步切换配置）
            load_to_account(account.account_id)
            log.info(f"账号已切换: {account.account_name}({account.account_id})")
            # 运行前重新加载配置
            cfg._load_config()
            _run_tasks_once(task)
        except Exception as e:
            success = False
            log.error(f"账号 {account.account_name}({account.account_id}) 运行失败: {e}")
            # 确保游戏被关闭再继续下一个
            try:
                get_game_controller().stop_game()
            except Exception:
                pass
            _notify(f"[多账号连跑] 账号 {account.account_name}({account.account_id}) 运行失败: {e}",
                    NotificationLevel.ERROR)
            if stop_on_error:
                log.error("已启用 stop_on_error，停止后续账号")
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
    _notify(summary)
    log.hr("多账号连跑结束", 0)
    if pause_when_done:
        pause_on_success()
    return all(ok for _, ok, _ in results)
