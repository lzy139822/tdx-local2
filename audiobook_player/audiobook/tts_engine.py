"""edge-tts 语音引擎封装：多音色、语速调节、生成 MP3、流式播放"""
import asyncio
import os
import re
import sys
from typing import List, Optional

# 常用中文音色（edge-tts）
DEFAULT_CN_VOICES = [
    ("zh-CN-XiaoxiaoNeural", "晓晓（女声，温柔）"),
    ("zh-CN-YunxiNeural", "云希（男声，阳光）"),
    ("zh-CN-YunjianNeural", "云健（男声，沉稳）"),
    ("zh-CN-XiaoyiNeural", "晓伊（女声，活力）"),
    ("zh-CN-YunyangNeural", "云扬（男声，新闻）"),
    ("zh-CN-XiaochenNeural", "晓辰（女声，知性）"),
    ("zh-CN-XiaohanNeural", "晓涵（女声，亲切）"),
    ("zh-CN-YunxiaNeural", "云夏（男声，少年）"),
    ("zh-HK-HiuMaanNeural", "曉曼（粤语女声）"),
    ("zh-TW-HsiaoChenNeural", "曉臻（台语女声）"),
]


def get_voice_list() -> List[tuple]:
    """获取常用中文音色列表"""
    return list(DEFAULT_CN_VOICES)


def _get_proxy() -> Optional[str]:
    """自动检测环境变量中的代理（edge-tts 需要显式传入）"""
    for env in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        v = os.environ.get(env)
        if v:
            return v
    return None


async def list_all_voices() -> list:
    """列出 edge-tts 所有可用音色"""
    import edge_tts
    voices = await edge_tts.list_voices()
    return voices


def _normalize_rate(rate: str) -> str:
    """标准化语速参数。支持 '1.0' / '+50%' / '-20%' / 数字"""
    if rate is None:
        return "+0%"
    if isinstance(rate, (int, float)):
        # 1.0 = 正常，>1 加速，<1 减速
        pct = int((rate - 1.0) * 100)
        return f"{pct:+d}%"
    s = str(rate).strip()
    if s.endswith("%"):
        if s.startswith(("+", "-")):
            return s
        return f"+{s}"
    # 纯数字
    try:
        v = float(s)
        pct = int((v - 1.0) * 100)
        return f"{pct:+d}%"
    except ValueError:
        return s if s.startswith(("+", "-")) else f"+{s}"


async def text_to_speech(text: str, output_file: str,
                         voice: str = "zh-CN-XiaoxiaoNeural",
                         rate: str = "+0%", volume: str = "+0%"):
    """将文本转语音并保存到文件"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume, proxy=_get_proxy())
    await communicate.save(output_file)


async def stream_to_file(text: str, output_file: str,
                         voice: str = "zh-CN-XiaoxiaoNeural",
                         rate: str = "+0%"):
    """流式生成并保存（适合长文本，边下边写）"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate, proxy=_get_proxy())
    with open(output_file, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])


async def generate_chapter_audio(chapter_content: str, output_file: str,
                                 voice: str = "zh-CN-XiaoxiaoNeural",
                                 rate: str = "+0%",
                                 max_chunk: int = 2000):
    """将一个章节内容生成完整 MP3。长文本自动分块后用 ffmpeg 拼接。"""
    from .chapter_parser import split_long_text

    chunks = split_long_text(chapter_content, max_chunk)
    if len(chunks) == 1:
        await stream_to_file(chunks[0], output_file, voice, rate)
        return

    # 分块生成临时文件
    tmp_files = []
    try:
        for i, chunk in enumerate(chunks):
            tmp = output_file + f".part{i}.mp3"
            await stream_to_file(chunk, tmp, voice, rate)
            tmp_files.append(tmp)
        _concat_mp3(tmp_files, output_file)
    finally:
        for f in tmp_files:
            if os.path.exists(f):
                os.remove(f)


def _concat_mp3(files: List[str], output: str):
    """用 ffmpeg 拼接多个 mp3；若没有 ffmpeg 则直接二进制拼接（mp3 可直接拼接）"""
    if not files:
        return
    try:
        import subprocess
        # 生成 concat 文件列表
        list_file = output + ".concat.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for fn in files:
                f.write(f"file '{os.path.abspath(fn)}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", list_file, "-c", "copy", output],
            check=True, capture_output=True,
        )
        os.remove(list_file)
    except (FileNotFoundError, subprocess.CalledProcessError):
        # 退化为直接拼接（MP3 格式允许简单拼接）
        with open(output, "wb") as out:
            for fn in files:
                with open(fn, "rb") as inp:
                    out.write(inp.read())


def play_audio(file_path: str, backend: str = "auto"):
    """播放音频文件。backend: auto / pygame / playsound / system"""
    if backend == "auto":
        for b in ("pygame", "playsound", "system"):
            try:
                play_audio(file_path, b)
                return
            except Exception:
                continue
        raise RuntimeError("没有可用的播放后端，请安装 pygame: pip install pygame")
    elif backend == "pygame":
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    elif backend == "playsound":
        from playsound import playsound
        playsound(file_path)
    elif backend == "system":
        import subprocess
        if os.name == "nt":
            os.startfile(file_path)  # type: ignore
        elif sys.platform == "darwin":
            subprocess.run(["afplay", file_path])
        else:
            for cmd in (["mpg123", file_path], ["mpg321", file_path],
                        ["ffplay", "-nodisp", "-autoexit", file_path],
                        ["aplay", file_path]):
                try:
                    subprocess.run(cmd, check=True)
                    return
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
            raise RuntimeError("系统未找到音频播放器")
