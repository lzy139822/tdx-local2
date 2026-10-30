# -*- coding: utf-8 -*-
"""听书 App - Kivy 移动端

功能：
- 打开电子书（TXT / EPUB / PDF）
- 章节列表导航
- 播放 / 暂停 / 停止 / 上一章 / 下一章
- 音色选择、语速调节
- 断点续听
- 导出章节 MP3
"""
import asyncio
import os
import sys
import tempfile
import threading

# Kivy 配置（放在 import 之前）
from kivy.config import Config
Config.set("kivy", "keyboard_mode", "system")
Config.set("graphics", "width", "400")
Config.set("graphics", "height", "700")

from kivy.app import App
from kivy.core.audio import SoundLoader
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.slider import Slider
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.utils import platform

# 导入核心模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audiobook.text_extractor import extract_text
from audiobook.chapter_parser import parse_chapters
from audiobook.tts_engine import get_voice_list, generate_chapter_audio, _normalize_rate
from audiobook.progress import save_progress, get_progress

# 移动端状态目录
if platform == "android":
    from android.storage import app_storage_path  # type: ignore
    os.environ["AUDIOBOOK_STATE_DIR"] = os.path.join(app_storage_path(), "audiobook")
else:
    os.environ.setdefault("AUDIOBOOK_STATE_DIR",
                          os.path.join(os.path.expanduser("~"), ".audiobook_player"))


# 音色列表
VOICE_LIST = get_voice_list()
VOICE_IDS = [v[0] for v in VOICE_LIST]
VOICE_NAMES = [v[1] for v in VOICE_LIST]
VOICE_MAP = dict(zip(VOICE_NAMES, VOICE_IDS))


def run_async(coro, callback=None):
    """在后台线程运行 asyncio 协程，回调在主线程执行"""
    def worker():
        try:
            result = asyncio.run(coro)
            if callback:
                Clock.schedule_once(lambda dt: callback(result), 0)
        except Exception as e:
            if callback:
                Clock.schedule_once(lambda dt: callback(Exception(str(e))), 0)
    threading.Thread(target=worker, daemon=True).start()


class AudiobookApp(App):
    title = "听书"

    def build(self):
        self.chapters = []
        self.current_idx = 0
        self.file_path = None
        self.sound = None
        self.is_generating = False
        self.tmp_audio = None
        self._manual_stop = False  # 区分手动停止与自然播放结束

        root = BoxLayout(orientation="vertical", padding=10, spacing=8)

        # 顶部：打开文件
        top = BoxLayout(size_hint_y=None, height=50, spacing=8)
        self.open_btn = Button(text="📂 打开电子书", font_size="15sp",
                               background_color=(0.4, 0.49, 0.92, 1))
        self.open_btn.bind(on_press=self.open_file)
        top.add_widget(self.open_btn)
        root.add_widget(top)

        # 控制区：音色 + 语速
        ctrl = BoxLayout(size_hint_y=None, height=50, spacing=8)
        self.voice_spinner = Spinner(text=VOICE_NAMES[0], values=VOICE_NAMES,
                                     font_size="12sp", size_hint_x=1.2)
        self.rate_label = Label(text="语速 1.0x", size_hint_x=None, width=80,
                                font_size="12sp")
        self.rate_slider = Slider(min=0.5, max=2.0, value=1.0, step=0.1)
        self.rate_slider.bind(value=self.on_rate_change)
        ctrl.add_widget(self.voice_spinner)
        ctrl.add_widget(self.rate_label)
        ctrl.add_widget(self.rate_slider)
        root.add_widget(ctrl)

        # 章节列表
        self.info_label = Label(text="请打开一本电子书", size_hint_y=None, height=30,
                                font_size="13sp", color=(0.5, 0.5, 0.5, 1))
        root.add_widget(self.info_label)

        list_scroll = ScrollView()
        self.chapter_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=2)
        self.chapter_box.bind(minimum_height=self.chapter_box.setter("height"))
        list_scroll.add_widget(self.chapter_box)
        root.add_widget(list_scroll)

        # 底部播放控制
        player = BoxLayout(orientation="vertical", size_hint_y=None, height=110, spacing=4)
        self.now_label = Label(text="未播放", font_size="13sp",
                               size_hint_y=None, height=24)
        player.add_widget(self.now_label)

        btns = BoxLayout(size_hint_y=None, height=50, spacing=4)
        for text, cb in [("⏮", self.prev_chapter), ("▶", self.play_current),
                         ("⏸", self.pause_audio), ("⏹", self.stop_audio),
                         ("⏭", self.next_chapter), ("💾", self.download_chapter)]:
            b = Button(text=text, font_size="16sp")
            b.bind(on_press=cb)
            btns.add_widget(b)
        player.add_widget(btns)

        self.status_label = Label(text="就绪", font_size="11sp",
                                  color=(0.4, 0.4, 0.4, 1), size_hint_y=None, height=20)
        player.add_widget(self.status_label)
        root.add_widget(player)

        return root

    def set_status(self, msg):
        self.status_label.text = msg

    def get_voice(self):
        return VOICE_MAP.get(self.voice_spinner.text, VOICE_IDS[0])

    def get_rate(self):
        return _normalize_rate(str(self.rate_slider.value))

    def on_rate_change(self, instance, value):
        self.rate_label.text = f"语速 {value:.1f}x"

    # ---------- 文件选择 ----------
    def open_file(self, *args):
        if platform == "android":
            self._open_file_android()
        else:
            self._open_file_desktop()

    def _open_file_desktop(self):
        content = BoxLayout(orientation="vertical")
        chooser = FileChooserListView(filters=["*.txt", "*.epub", "*.pdf"],
                                      path=os.path.expanduser("~"))
        btn_box = BoxLayout(size_hint_y=None, height=40)
        cancel = Button(text="取消")
        select = Button(text="选择")
        btn_box.add_widget(cancel)
        btn_box.add_widget(select)
        content.add_widget(chooser)
        content.add_widget(btn_box)
        popup = Popup(title="选择电子书", content=content, size_hint=(0.9, 0.9))
        cancel.bind(on_press=popup.dismiss)
        select.bind(on_press=lambda *a: self._load_file(chooser.selection[0] if chooser.selection else None, popup))
        popup.open()

    def _open_file_android(self):
        """Android 上用 plyer 选择文件"""
        try:
            from plyer import filechooser
            filechooser.open_file(on_selection=self._on_android_file,
                                  filters=["*.txt", "*.epub", "*.pdf"])
        except ImportError:
            self.set_status("需要安装 plyer: pip install plyer")
            self._open_file_desktop()

    def _on_android_file(self, selection):
        if selection:
            self._load_file(selection[0], None)

    def _load_file(self, path, popup):
        if popup:
            popup.dismiss()
        if not path:
            return
        self.file_path = path
        self.set_status(f"正在解析: {os.path.basename(path)}")
        try:
            text = extract_text(path)
            self.chapters = parse_chapters(text)
        except Exception as e:
            self.set_status(f"解析失败: {e}")
            return

        # 渲染章节列表
        self.chapter_box.clear_widgets()
        for c in self.chapters:
            btn = Button(text=f"{c.index+1}. {c.title}",
                         size_hint_y=None, height=44,
                         font_size="13sp", halign="left", valign="middle")
            btn.bind(size=btn.setter("text_size"))
            btn.bind(on_press=lambda inst, idx=c.index: self.play_chapter(idx))
            self.chapter_box.add_widget(btn)

        self.info_label.text = f"共 {len(self.chapters)} 章"
        self.set_status(f"已加载 {len(self.chapters)} 章")

        # 断点续听
        prog = get_progress(path)
        if prog and prog.get("chapter", 0) < len(self.chapters):
            self.current_idx = prog["chapter"]
            self.set_status(f"上次听到第 {self.current_idx+1} 章，点击播放继续")

    # ---------- 播放控制 ----------
    def play_current(self, *args):
        if not self.chapters:
            self.set_status("请先打开一本书")
            return
        self.play_chapter(self.current_idx)

    def play_chapter(self, idx):
        if idx < 0 or idx >= len(self.chapters):
            return
        if self.is_generating:
            self.set_status("正在生成音频，请稍候...")
            return
        self.current_idx = idx
        self.now_label.text = f"正在播放: {self.chapters[idx].title}"
        self.set_status("正在生成音频...")
        self.is_generating = True

        # 停止旧音频
        self._stop_sound()

        # 生成临时音频文件
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        self.tmp_audio = tmp.name

        ch = self.chapters[idx]
        run_async(
            generate_chapter_audio(ch.content, tmp.name, self.get_voice(), self.get_rate()),
            callback=self._on_audio_ready,
        )

    def _on_audio_ready(self, result):
        self.is_generating = False
        if isinstance(result, Exception):
            self.set_status(f"生成失败: {result}")
            return
        self.set_status("生成完成，开始播放")
        self.sound = SoundLoader.load(self.tmp_audio)
        if self.sound:
            self._manual_stop = False
            # 播放结束时自动跳下一章
            self.sound.bind(on_stop=self._on_audio_finished)
            self.sound.play()
            # 保存进度
            if self.file_path:
                save_progress(self.file_path, self.current_idx,
                              voice=self.get_voice(), rate=self.get_rate())
        else:
            self.set_status("音频加载失败")

    def _on_audio_finished(self, *args):
        """音频播放结束回调：仅在自然结束时跳下一章"""
        if self._manual_stop:
            return
        if self.current_idx < len(self.chapters) - 1:
            self.play_chapter(self.current_idx + 1)

    def pause_audio(self, *args):
        if self.sound:
            self._manual_stop = True
            self.sound.stop()
            self.set_status("已暂停")

    def stop_audio(self, *args):
        self._stop_sound()
        self.now_label.text = "已停止"
        self.set_status("已停止")

    def _stop_sound(self):
        self._manual_stop = True
        if self.sound:
            try:
                self.sound.stop()
            except Exception:
                pass
            self.sound = None
        if self.tmp_audio and os.path.exists(self.tmp_audio):
            try:
                os.remove(self.tmp_audio)
            except Exception:
                pass
            self.tmp_audio = None

    def prev_chapter(self, *args):
        if self.current_idx > 0:
            self.play_chapter(self.current_idx - 1)

    def next_chapter(self, *args):
        if self.current_idx < len(self.chapters) - 1:
            self.play_chapter(self.current_idx + 1)

    # ---------- 导出 MP3 ----------
    def download_chapter(self, *args):
        if not self.chapters:
            self.set_status("请先打开一本书")
            return
        ch = self.chapters[self.current_idx]
        # 保存到应用目录或下载目录
        if platform == "android":
            from android.storage import primary_external_storage_path  # type: ignore
            out_dir = os.path.join(primary_external_storage_path(), "Download")
        else:
            out_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, f"{self.current_idx+1:04d}_{ch.title[:20]}.mp3")
        self.set_status("正在生成 MP3...")
        self.is_generating = True
        run_async(
            generate_chapter_audio(ch.content, out_file, self.get_voice(), self.get_rate()),
            callback=lambda r: self._on_download_done(r, out_file),
        )

    def _on_download_done(self, result, out_file):
        self.is_generating = False
        if isinstance(result, Exception):
            self.set_status(f"导出失败: {result}")
        else:
            self.set_status(f"已保存: {out_file}")

    def on_stop(self):
        self._stop_sound()


if __name__ == "__main__":
    AudiobookApp().run()
