"""桌面听书应用 - tkinter GUI

功能：
- 打开电子书（TXT/EPUB/PDF）
- 章节列表导航
- 播放 / 暂停 / 停止 / 上一章 / 下一章
- 音色选择、语速调节
- 断点续听
- 下载章节 MP3
"""
import asyncio
import os
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audiobook.text_extractor import extract_text
from audiobook.chapter_parser import parse_chapters
from audiobook.tts_engine import (
    get_voice_list, generate_chapter_audio, _normalize_rate,
)
from audiobook.progress import save_progress, get_progress

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class AudiobookApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📚 智能听书 - 桌面版")
        self.root.geometry("780x620")
        self.root.configure(bg="#f0f2f5")

        self.chapters = []
        self.current_idx = 0
        self.file_path = None
        self.audio_file = None
        self.is_playing = False
        self.generating = False

        self._build_ui()
        if not PYGAME_AVAILABLE:
            self.status_var.set("⚠ 未安装 pygame，仅支持生成 MP3（pip install pygame）")

    def _build_ui(self):
        # 顶部工具栏
        top = tk.Frame(self.root, bg="#667eea", height=56)
        top.pack(fill="x")
        tk.Button(top, text="📂 打开书籍", command=self.open_file,
                  bg="#5568d3", fg="white", relief="flat",
                  font=("Microsoft YaHei", 11), padx=16, pady=8).pack(side="left", padx=12, pady=10)
        tk.Button(top, text="💾 下载本章 MP3", command=self.download_chapter,
                  bg="#5568d3", fg="white", relief="flat",
                  font=("Microsoft YaHei", 11), padx=16, pady=8).pack(side="left", padx=4, pady=10)

        self.status_var = tk.StringVar(value="请打开一本电子书开始听书")
        tk.Label(top, textvariable=self.status_var, bg="#667eea", fg="white",
                 font=("Microsoft YaHei", 10)).pack(side="right", padx=16)

        # 控制面板
        ctrl = tk.Frame(self.root, bg="white", pady=12)
        ctrl.pack(fill="x", padx=16, pady=(12, 0))

        tk.Label(ctrl, text="音色:", bg="white", font=("Microsoft YaHei", 10)).grid(row=0, column=0, padx=6)
        self.voice_var = tk.StringVar(value="zh-CN-XiaoxiaoNeural")
        voice_cb = ttk.Combobox(ctrl, textvariable=self.voice_var, state="readonly", width=28)
        voice_cb["values"] = [f"{v[0]}  {v[1]}" for v in get_voice_list()]
        voice_cb.current(0)
        voice_cb.grid(row=0, column=1, padx=6)

        tk.Label(ctrl, text="语速:", bg="white", font=("Microsoft YaHei", 10)).grid(row=0, column=2, padx=(16, 6))
        self.rate_var = tk.DoubleVar(value=1.0)
        rate_scale = tk.Scale(ctrl, from_=0.5, to=2.0, resolution=0.1, orient="horizontal",
                              variable=self.rate_var, length=120, bg="white", highlightthickness=0)
        rate_scale.grid(row=0, column=3, padx=6)

        # 章节列表
        list_frame = tk.Frame(self.root, bg="white")
        list_frame.pack(fill="both", expand=True, padx=16, pady=12)

        tk.Label(list_frame, text="📖 章节目录", bg="white", font=("Microsoft YaHei", 11, "bold"),
                 anchor="w").pack(fill="x", padx=12, pady=(10, 4))

        self.chapter_listbox = tk.Listbox(list_frame, font=("Microsoft YaHei", 10),
                                          activestyle="none", selectbackground="#667eea",
                                          selectforeground="white", relief="flat", bd=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.chapter_listbox.yview)
        self.chapter_listbox.configure(yscrollcommand=scrollbar.set)
        self.chapter_listbox.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 10))
        scrollbar.pack(side="right", fill="y", padx=(0, 12), pady=(0, 10))
        self.chapter_listbox.bind("<<ListboxSelect>>", self.on_chapter_select)

        # 底部播放控制
        player = tk.Frame(self.root, bg="#2d3436", height=90)
        player.pack(fill="x", side="bottom")

        self.now_playing = tk.StringVar(value="未播放")
        tk.Label(player, textvariable=self.now_playing, bg="#2d3436", fg="white",
                 font=("Microsoft YaHei", 10)).pack(pady=(10, 0))

        btns = tk.Frame(player, bg="#2d3436")
        btns.pack(pady=8)
        for text, cmd in [("⏮", self.prev_chapter), ("▶ 播放", self.play_current),
                          ("⏸ 暂停", self.pause_audio), ("⏹ 停止", self.stop_audio),
                          ("⏭", self.next_chapter)]:
            tk.Button(btns, text=text, command=cmd, bg="#667eea", fg="white",
                      relief="flat", font=("Microsoft YaHei", 10), padx=14, pady=6).pack(side="left", padx=4)

    def set_status(self, msg):
        self.status_var.set(msg)
        self.root.update_idletasks()

    def open_file(self):
        path = filedialog.askopenfilename(
            title="选择电子书",
            filetypes=[("电子书", "*.txt *.epub *.pdf"), ("所有文件", "*.*")]
        )
        if not path:
            return
        self.file_path = path
        self.set_status(f"正在解析: {os.path.basename(path)}")
        try:
            text = extract_text(path)
            self.chapters = parse_chapters(text)
        except Exception as e:
            messagebox.showerror("错误", f"解析失败: {e}")
            return

        self.chapter_listbox.delete(0, tk.END)
        for c in self.chapters:
            self.chapter_listbox.insert(tk.END, f"{c.index+1}. {c.title}")
        self.set_status(f"已加载 {len(self.chapters)} 章")

        # 断点续听
        prog = get_progress(path)
        if prog and prog.get("chapter", 0) < len(self.chapters):
            if messagebox.askyesno("断点续听", f"上次听到第 {prog['chapter']+1} 章，是否继续？"):
                self.current_idx = prog["chapter"]
                if prog.get("voice"):
                    for i, v in enumerate(get_voice_list()):
                        if v[0] == prog["voice"]:
                            self.voice_var.set(f"{v[0]}  {v[1]}")
                            break
                self.chapter_listbox.selection_clear(0, tk.END)
                self.chapter_listbox.selection_set(self.current_idx)
                self.chapter_listbox.see(self.current_idx)

    def get_voice(self):
        val = self.voice_var.get()
        return val.split("  ")[0] if "  " in val else val

    def get_rate(self):
        return _normalize_rate(str(self.rate_var.get()))

    def on_chapter_select(self, event):
        sel = self.chapter_listbox.curselection()
        if sel:
            self.current_idx = sel[0]

    def play_current(self):
        if not self.chapters:
            messagebox.showinfo("提示", "请先打开一本书")
            return
        if self.generating:
            return
        self.play_chapter(self.current_idx)

    def play_chapter(self, idx):
        if idx < 0 or idx >= len(self.chapters):
            return
        self.current_idx = idx
        self.chapter_listbox.selection_clear(0, tk.END)
        self.chapter_listbox.selection_set(idx)
        self.chapter_listbox.see(idx)

        ch = self.chapters[idx]
        self.now_playing.set(f"正在播放: {ch.title}")
        self.set_status("正在生成音频...")
        self.generating = True

        # 后台生成音频
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()

        def generate():
            try:
                asyncio.run(generate_chapter_audio(
                    ch.content, tmp.name, self.get_voice(), self.get_rate()
                ))
                self.audio_file = tmp.name
                self.root.after(0, self._start_playback)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"生成失败: {e}"))
                self.set_status("生成失败")
            finally:
                self.generating = False

        threading.Thread(target=generate, daemon=True).start()

    def _start_playback(self):
        if not PYGAME_AVAILABLE or not self.audio_file:
            self.set_status("需要 pygame 才能播放，已生成音频文件")
            return
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(self.audio_file)
            pygame.mixer.music.play()
            self.is_playing = True
            self.set_status("播放中...")
            self._check_playback_end()
            # 保存进度
            if self.file_path:
                save_progress(self.file_path, self.current_idx,
                              voice=self.get_voice(), rate=self.get_rate())
        except Exception as e:
            messagebox.showerror("播放错误", str(e))

    def _check_playback_end(self):
        if PYGAME_AVAILABLE and self.is_playing:
            if not pygame.mixer.music.get_busy():
                self.is_playing = False
                self.next_chapter()
                return
        self.root.after(1000, self._check_playback_end)

    def pause_audio(self):
        if PYGAME_AVAILABLE and self.is_playing:
            pygame.mixer.music.pause()
            self.is_playing = False
            self.set_status("已暂停")

    def stop_audio(self):
        if PYGAME_AVAILABLE:
            pygame.mixer.music.stop()
        self.is_playing = False
        self.now_playing.set("已停止")
        self.set_status("已停止")

    def next_chapter(self):
        if self.current_idx < len(self.chapters) - 1:
            self.play_chapter(self.current_idx + 1)

    def prev_chapter(self):
        if self.current_idx > 0:
            self.play_chapter(self.current_idx - 1)

    def download_chapter(self):
        if not self.chapters:
            messagebox.showinfo("提示", "请先打开一本书")
            return
        ch = self.chapters[self.current_idx]
        save_path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            initialfile=f"{self.current_idx+1:04d}_{ch.title[:30]}.mp3",
            filetypes=[("MP3", "*.mp3")]
        )
        if not save_path:
            return
        self.set_status("正在生成 MP3...")
        self.generating = True

        def generate():
            try:
                asyncio.run(generate_chapter_audio(
                    ch.content, save_path, self.get_voice(), self.get_rate()
                ))
                self.root.after(0, lambda: messagebox.showinfo("完成", f"已保存: {save_path}"))
                self.set_status("MP3 生成完成")
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", str(e)))
            finally:
                self.generating = False

        threading.Thread(target=generate, daemon=True).start()


def main():
    root = tk.Tk()
    app = AudiobookApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
