# -*- coding: utf-8 -*-
"""
按账号保存配置（可选功能）

启用后（开关在「账号」页），配置文件中与游戏内容相关的部分会跟随当前登录账号切换；
与运行环境相关的全局设置始终共用一份，不会因为换号而变化。

文件布局：
    settings/accounts/profile_config.yaml   开关状态与当前已载入的账号
    settings/accounts/configs/<UID>.yaml    每个账号自己的配置

行为约定：
    - 开关关闭时：任何函数都不改动任何文件，行为与官方原版完全一致。
    - 开关打开时：
        1. 切号前，先把当前 config.yaml 存回它所属的账号文件；
        2. 再载入目标账号的配置（全局项仍取当前 config.yaml 的值）；
        3. 目标账号还没有配置时，用官方默认配置（config.example.yaml）生成一份。
    - 首次打开开关的那一刻，会把正在使用的 config.yaml 原样保存为当前账号的配置，
      避免已经调好的设置丢失（仅在「打开开关」时发生，不是新账号的默认行为）。

全局项（不随账号切换）的判定见 is_global_key()：白名单键 + 前缀族。
若官方后续新增了环境类配置项而未列入，它会变成「随账号走」——此时把它加进
GLOBAL_KEYS / GLOBAL_KEY_PREFIXES 即可。
"""

import os

from ruamel.yaml import YAML

from module.logger import log
from utils.registry.gameaccount import gamereg_uid

_YAML = YAML()

ACCOUNT_DIR = "settings/accounts"
CONFIG_DIR = os.path.join(ACCOUNT_DIR, "configs")
STATE_FILE = os.path.join(ACCOUNT_DIR, "profile_config.yaml")
CONFIG_PATH = "config.yaml"
EXAMPLE_PATH = os.path.join("assets", "config", "config.example.yaml")

# 全局项前缀族：这些名字开头的配置一律不随账号走
GLOBAL_KEY_PREFIXES = (
    "browser_",
    "cloud_game_",
    "launcher_",
    "log_",
    "notify_",
    "window_",
    "hotkey_",
    "scheduled_",
    "telemetry_",
    "update_",
)

# 全局项白名单：与运行环境、界面、更新、通知频道、调度相关的配置
GLOBAL_KEYS = {
    "locales",
    "ui_language",
    "debug_mode_enable",
    "check_update",
    "pause_after_success",
    "exit_after_failure",
    "after_finish",
    "play_audio",
    "python_exe_path",
    "pypi_mirror_urls",
    "game_title_name",
    "game_process_name",
    "game_path",
    "update_via_launcher",
    "start_game_timeout",
    "update_game_timeout",
    "auto_set_game_path_enable",
    "auto_set_resolution_enable",
    "ocr_gpu_acceleration",
    "use_background_screenshot",
    "genshin_starRail_fps_unlocker_allow",
    "genshin_starRail_fps_unlocker_path",
    "loop_mode",
    "scheduled_time",
    "power_limit",
    "refresh_hour",
    "script_path",
    "banner_path",
    "home_cards",
    "close_window_action",
    "notification_enable",
    "notify_level",
    "notify_merge",
    "notify_send_images",
    "auto_update",
    "mirrorchyan_cdk",
}


def is_global_key(key: str) -> bool:
    """该配置项是否属于「全局项」（不随账号切换）"""
    return key in GLOBAL_KEYS or key.startswith(GLOBAL_KEY_PREFIXES)


def _ensure_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def _read(path):
    """读取 YAML 文件，失败或为空时返回 None"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return _YAML.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        log.error(f"[按账号配置] 读取 {path} 失败: {e}")
        return None


def _write(path, data):
    """写入 YAML 文件（先写临时文件再替换，避免中断产生损坏文件）"""
    _ensure_dirs()
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            _YAML.dump(data, f)
        os.replace(tmp, path)
        return True
    except Exception as e:
        log.error(f"[按账号配置] 写入 {path} 失败: {e}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False


# --------------------------------------------------------------------------
# 开关状态
# --------------------------------------------------------------------------

def _load_state() -> dict:
    data = _read(STATE_FILE)
    if not isinstance(data, dict):
        data = {}
    data.setdefault("config_follows_account", False)
    data.setdefault("loaded_account", None)
    return data


def _save_state(state: dict):
    _write(STATE_FILE, state)


def is_enabled() -> bool:
    """「配置跟随账号」开关是否打开"""
    return bool(_load_state().get("config_follows_account", False))


def get_loaded_account():
    """当前 config.yaml 属于哪个账号（None 表示未记录）"""
    value = _load_state().get("loaded_account")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def set_enabled(enabled: bool, adopt_current: bool = True) -> bool:
    """
    打开/关闭「配置跟随账号」。

    打开时默认把当前正在使用的 config.yaml 保存为当前账号的配置（避免丢失已有设置）。
    关闭时只停止跟随，不会删除任何已保存的账号配置。
    """
    state = _load_state()
    if enabled:
        state["config_follows_account"] = True
        if adopt_current:
            uid = gamereg_uid()
            live = _read(CONFIG_PATH)
            if uid is not None and live is not None:
                if os.path.exists(config_path_of(uid)):
                    log.info(f"[按账号配置] 账号 {uid} 已有配置文件，将用当前配置覆盖")
                if _write(config_path_of(uid), _account_part(live)):
                    state["loaded_account"] = int(uid)
                    log.info(f"[按账号配置] 已启用，当前配置已保存为账号 {uid} 的配置")
        _save_state(state)
        return True

    state["config_follows_account"] = False
    state["loaded_account"] = None
    _save_state(state)
    log.info("[按账号配置] 已关闭，配置文件恢复为所有账号共用")
    return False


# --------------------------------------------------------------------------
# 账号配置文件
# --------------------------------------------------------------------------

def config_path_of(uid) -> str:
    return os.path.join(CONFIG_DIR, f"{uid}.yaml")


def has_account_config(uid) -> bool:
    return uid is not None and os.path.exists(config_path_of(uid))


def _account_part(config) -> dict:
    """从一份完整配置里取出「账号项」（剔除全局项）"""
    part = config.copy()
    for key in [k for k in part.keys() if is_global_key(k)]:
        del part[key]
    return part


def _default_account_part() -> dict:
    """官方默认配置里的账号项（用于新账号首次初始化）"""
    example = _read(EXAMPLE_PATH)
    if not isinstance(example, dict):
        log.error("[按账号配置] 读取官方默认配置失败")
        return {}
    return _account_part(example)


def _merge_live_with_account(live, account_part):
    """用账号项替换 config.yaml 中的对应部分，全局项原样保留"""
    merged = live.copy()
    for key in [k for k in merged.keys() if not is_global_key(k)]:
        del merged[key]
    for key, value in account_part.items():
        if not is_global_key(key):
            merged[key] = value
    return merged


def _reload_cfg():
    """把磁盘上的 config.yaml 重新读进内存配置对象"""
    try:
        from module.config import cfg
        cfg._load_config()
    except Exception as e:
        log.error(f"[按账号配置] 重新加载配置失败: {e}")


def _load_into_live(uid, live) -> bool:
    """把账号 uid 的配置合入 config.yaml 并重新载入内存配置"""
    account_part = _read(config_path_of(uid))
    if not isinstance(account_part, dict):
        log.error(f"[按账号配置] 账号 {uid} 的配置文件无法读取")
        return False
    if not _write(CONFIG_PATH, _merge_live_with_account(live, account_part)):
        return False
    _reload_cfg()
    return True


def sync_to(uid) -> bool:
    """
    把 config.yaml 切换为账号 uid 的配置（幂等：已经是该账号则什么都不做）。

    由切号流程与每次运行前调用，返回 True 表示本次确实做了切换。
    """
    if not is_enabled():
        return False
    if uid is None:
        return False
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return False

    state = _load_state()
    loaded = state.get("loaded_account")
    try:
        loaded = int(loaded) if loaded is not None else None
    except (TypeError, ValueError):
        loaded = None

    if loaded == uid:
        return False

    live = _read(CONFIG_PATH)
    if not isinstance(live, dict):
        log.error("[按账号配置] 当前 config.yaml 无法读取，跳过配置切换")
        return False

    target = config_path_of(uid)
    target_exists = os.path.exists(target)

    # 1) 把当前 config.yaml 存回它所属的账号
    if loaded is not None:
        _write(config_path_of(loaded), _account_part(live))

    # 2) 载入目标账号的配置
    if target_exists:
        if not _load_into_live(uid, live):
            return False
        log.info(f"[按账号配置] 已切换到账号 {uid} 的配置")
    elif loaded is None:
        # 尚未记录归属（例如从未记录过就切号）：把当前配置收留给该账号，避免丢设置
        if not _write(target, _account_part(live)):
            return False
        log.info(f"[按账号配置] 已把当前配置保存为账号 {uid} 的配置")
    else:
        # 新账号：用官方默认配置初始化
        if not _write(target, _default_account_part()):
            return False
        if not _load_into_live(uid, live):
            return False
        log.info(f"[按账号配置] 账号 {uid} 首次使用，已按官方默认配置初始化")

    state["loaded_account"] = uid
    _save_state(state)
    return True


def sync_current() -> bool:
    """按注册表里当前登录的账号切换配置（运行前调用）"""
    if not is_enabled():
        return False
    return sync_to(gamereg_uid())


def copy_account_config(src_uid, dst_uid) -> bool:
    """
    把 src_uid 的配置复制到 dst_uid。src_uid 为 None 时使用官方默认配置。
    若目标正是当前正在使用的账号，立即生效。
    """
    if dst_uid is None:
        return False
    try:
        dst_uid = int(dst_uid)
        src_uid = int(src_uid) if src_uid is not None else None
    except (TypeError, ValueError):
        return False

    if src_uid is None:
        data = _default_account_part()
    elif has_account_config(src_uid):
        data = _read(config_path_of(src_uid))
    else:
        log.error(f"[按账号配置] 账号 {src_uid} 没有可复制的配置")
        return False

    if not isinstance(data, dict):
        log.error("[按账号配置] 复制配置失败：源配置不可读")
        return False

    if not _write(config_path_of(dst_uid), data):
        return False

    if get_loaded_account() == dst_uid:
        live = _read(CONFIG_PATH)
        if isinstance(live, dict):
            _load_into_live(dst_uid, live)

    log.info("[按账号配置] 配置已复制到账号 " + str(dst_uid))
    return True
