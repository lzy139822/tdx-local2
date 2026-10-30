"""Audiobook CLI - 电子书听书命令行工具

用法示例:
  python cli.py listen 小说.txt                    # 听书（默认晓晓，正常语速）
  python cli.py listen 小说.txt --voice zh-CN-YunxiNeural --rate 1.2
  python cli.py mp3 小说.txt -o output_dir          # 生成每章 MP3
  python cli.py mp3 小说.txt --single -o book.mp3   # 整本合成一个 MP3
  python cli.py voices                              # 列出可用中文音色
  python cli.py progress                            # 查看断点续听记录
"""
import argparse
import asyncio
import os
import sys
import tempfile

# 确保包路径可用
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audiobook.text_extractor import extract_text
from audiobook.chapter_parser import parse_chapters
from audiobook.tts_engine import (
    get_voice_list, stream_to_file, generate_chapter_audio,
    play_audio, _normalize_rate,
)
from audiobook.progress import (
    save_progress, get_progress, list_progress, clear_progress,
)


def cmd_voices(args):
    """列出常用中文音色"""
    print("\n可用中文音色（edge-tts）:\n")
    for vid, desc in get_voice_list():
        print(f"  {vid:35s}  {desc}")
    print("\n提示：也可使用 edge-tts 支持的其他音色 ID。")


def cmd_progress(args):
    """查看断点续听进度"""
    state = list_progress()
    if not state:
        print("暂无播放记录。")
        return
    print("\n播放进度记录:\n")
    for key, info in state.items():
        print(f"  📖 {info.get('file', key)}")
        print(f"     章节: {info.get('chapter', 0)}  位置: {info.get('position', 0):.1f}s  "
              f"音色: {info.get('voice', '-')}  语速: {info.get('rate', '-')}")
        print()
    if args.clear:
        for key in state:
            clear_progress(key.replace(os.path.basename(key), ""))
        print("已清除所有记录。")


def cmd_listen(args):
    """听书模式：逐章生成并播放"""
    file_path = args.file
    if not os.path.exists(file_path):
        print(f"错误：文件不存在 {file_path}")
        sys.exit(1)

    print(f"正在读取文件: {file_path}")
    text = extract_text(file_path)
    chapters = parse_chapters(text)
    print(f"共解析 {len(chapters)} 章")

    voice = args.voice
    rate = _normalize_rate(args.rate)

    # 断点续听
    start_idx = 0
    prog = get_progress(file_path)
    if prog and not args.no_resume:
        start_idx = prog.get("chapter", 0)
        voice = prog.get("voice") or voice
        rate = prog.get("rate") or rate
        print(f"从上次进度继续：第 {start_idx + 1} 章")

    for i in range(start_idx, len(chapters)):
        ch = chapters[i]
        print(f"\n[{i+1}/{len(chapters)}] {ch.title}")
        if not ch.content.strip():
            continue

        # 生成临时音频
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        try:
            asyncio.run(stream_to_file(ch.content, tmp.name, voice, rate))
            save_progress(file_path, i, voice=voice, rate=rate)
            play_audio(tmp.name)
        except KeyboardInterrupt:
            save_progress(file_path, i, voice=voice, rate=rate)
            print(f"\n已中断，进度已保存（第 {i+1} 章）。")
            break
        except Exception as e:
            print(f"  播放失败: {e}")
        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)

    save_progress(file_path, len(chapters), voice=voice, rate=rate)
    print("\n✅ 全部播放完毕！")


def cmd_mp3(args):
    """生成 MP3 文件"""
    file_path = args.file
    if not os.path.exists(file_path):
        print(f"错误：文件不存在 {file_path}")
        sys.exit(1)

    print(f"正在读取文件: {file_path}")
    text = extract_text(file_path)
    chapters = parse_chapters(text)
    print(f"共解析 {len(chapters)} 章")

    voice = args.voice
    rate = _normalize_rate(args.rate)

    if args.single:
        # 整本合成一个 MP3
        full_text = "\n".join(ch.content for ch in chapters)
        output = args.output
        if os.path.isdir(output) or not output.endswith(".mp3"):
            output = os.path.join(output, f"{os.path.splitext(os.path.basename(file_path))[0]}.mp3")
        os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
        print(f"正在生成整本书 MP3: {output}")
        asyncio.run(generate_chapter_audio(full_text, output, voice, rate))
        print(f"✅ 已生成: {output}")
    else:
        # 每章一个 MP3
        out_dir = args.output
        if out_dir.endswith(".mp3"):
            out_dir = os.path.dirname(out_dir) or "."
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(file_path))[0]
        for i, ch in enumerate(chapters):
            safe_title = "".join(c for c in ch.title if c.isalnum() or c in " -_")[:40]
            out_file = os.path.join(out_dir, f"{base}_{i+1:04d}_{safe_title}.mp3")
            print(f"[{i+1}/{len(chapters)}] 生成: {os.path.basename(out_file)}")
            try:
                asyncio.run(generate_chapter_audio(ch.content, out_file, voice, rate))
            except Exception as e:
                print(f"  跳过（出错: {e}）")
        print(f"\n✅ 全部生成完毕，保存在: {out_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="电子书听书工具 - 支持 TXT/EPUB/PDF，edge-tts 语音合成"
    )
    sub = parser.add_subparsers(dest="command")

    # voices
    sub.add_parser("voices", help="列出可用中文音色")

    # progress
    p_prog = sub.add_parser("progress", help="查看断点续听进度")
    p_prog.add_argument("--clear", action="store_true", help="清除所有进度")

    # listen
    p_listen = sub.add_parser("listen", help="听书模式（逐章朗读）")
    p_listen.add_argument("file", help="电子书文件路径")
    p_listen.add_argument("--voice", default="zh-CN-XiaoxiaoNeural", help="音色 ID")
    p_listen.add_argument("--rate", default="1.0", help="语速（1.0 正常，1.5 快，0.8 慢）")
    p_listen.add_argument("--no-resume", action="store_true", help="不从上次进度继续")

    # mp3
    p_mp3 = sub.add_parser("mp3", help="生成 MP3 音频文件")
    p_mp3.add_argument("file", help="电子书文件路径")
    p_mp3.add_argument("-o", "--output", default="audio_output", help="输出目录或文件")
    p_mp3.add_argument("--voice", default="zh-CN-XiaoxiaoNeural", help="音色 ID")
    p_mp3.add_argument("--rate", default="1.0", help="语速")
    p_mp3.add_argument("--single", action="store_true", help="整本合成一个 MP3 文件")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    dispatch = {
        "voices": cmd_voices,
        "progress": cmd_progress,
        "listen": cmd_listen,
        "mp3": cmd_mp3,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
