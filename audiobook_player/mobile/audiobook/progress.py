"""进度管理：记录每本书的播放进度，实现断点续听"""
import json
import os
from typing import Dict, Optional

# 支持通过环境变量指定状态目录（Android 上需用应用私有目录）
STATE_DIR = os.environ.get(
    "AUDIOBOOK_STATE_DIR",
    os.path.join(os.path.expanduser("~"), ".audiobook_player"),
)
STATE_FILE = os.path.join(STATE_DIR, "progress.json")


def _ensure_dir():
    os.makedirs(STATE_DIR, exist_ok=True)


def _load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict):
    _ensure_dir()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _book_key(file_path: str) -> str:
    return os.path.abspath(file_path)


def save_progress(file_path: str, chapter_index: int,
                  position: float = 0.0, voice: str = "", rate: str = ""):
    """保存播放进度"""
    state = _load_state()
    key = _book_key(file_path)
    state[key] = {
        "chapter": chapter_index,
        "position": position,
        "voice": voice,
        "rate": rate,
        "file": os.path.basename(file_path),
    }
    _save_state(state)


def get_progress(file_path: str) -> Optional[dict]:
    """获取上次播放进度"""
    state = _load_state()
    return state.get(_book_key(file_path))


def clear_progress(file_path: str):
    """清除某本书的进度"""
    state = _load_state()
    key = _book_key(file_path)
    if key in state:
        del state[key]
        _save_state(state)


def list_progress() -> Dict[str, dict]:
    """列出所有有进度的书"""
    return _load_state()
