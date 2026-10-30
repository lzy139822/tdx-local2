# 📚 智能听书 - 电子书语音朗读工具

将电子书（TXT / EPUB / PDF）自动转成语音，支持**在线听书**、**生成 MP3**、**桌面播放器**和 **Web 网页版**。

基于微软 Edge 浏览器的免费 TTS 引擎（edge-tts），音质接近真人，支持多种中文音色、语速调节、章节导航、断点续听。

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 📖 多格式支持 | TXT、EPUB、PDF 自动识别解析 |
| 🎙️ 多音色 | 10+ 中文音色（普通话、粤语、台语） |
| ⚡ 语速调节 | 0.5x ~ 2.0x 自由调节 |
| 📑 章节导航 | 自动识别章节标题，按章跳转 |
| 🔖 断点续听 | 自动记住上次听到的位置 |
| 🎧 三种形态 | 命令行 / 桌面 GUI / Web 网页 |
| 💾 导出 MP3 | 单章或整本导出为 MP3 文件 |

## 🚀 快速开始

### 1. 安装依赖

```bash
cd audiobook_player
pip install -r requirements.txt
```

> 桌面听书和命令行听书需要音频播放后端，推荐安装 `pygame`：`pip install pygame`

### 2. 命令行听书

```bash
# 听书（默认晓晓，正常语速）
python cli.py listen 小说.txt

# 指定男声 + 1.5 倍速
python cli.py listen 小说.txt --voice zh-CN-YunxiNeural --rate 1.5

# 列出可用音色
python cli.py voices

# 查看断点续听记录
python cli.py progress
```

### 3. 生成 MP3 文件

```bash
# 每章一个 MP3（输出到 audio_output 目录）
python cli.py mp3 小说.txt -o audio_output

# 整本合成一个 MP3
python cli.py mp3 小说.txt --single -o 全书.mp3
```

### 4. Web 网页版

```bash
python web_app.py --port 5000
```

打开浏览器访问 `http://localhost:5000`，上传电子书即可在线听书，支持音色/语速切换、章节跳转、下载 MP3。

### 5. 桌面 GUI

```bash
python desktop_app.py
```

图形界面，支持播放/暂停/停止/上下章、音色选择、语速调节、下载 MP3。

## 🎵 可用中文音色

| 音色 ID | 说明 |
|---------|------|
| zh-CN-XiaoxiaoNeural | 晓晓（女声，温柔） |
| zh-CN-YunxiNeural | 云希（男声，阳光） |
| zh-CN-YunjianNeural | 云健（男声，沉稳） |
| zh-CN-XiaoyiNeural | 晓伊（女声，活力） |
| zh-CN-YunyangNeural | 云扬（男声，新闻） |
| zh-CN-XiaochenNeural | 晓辰（女声，知性） |
| zh-CN-XiaohanNeural | 晓涵（女声，亲切） |
| zh-CN-YunxiaNeural | 云夏（男声，少年） |
| zh-HK-HiuMaanNeural | 曉曼（粤语女声） |
| zh-TW-HsiaoChenNeural | 曉臻（台语女声） |

## 📂 项目结构

```
audiobook_player/
├── audiobook/
│   ├── __init__.py
│   ├── text_extractor.py   # 文本提取（TXT/EPUB/PDF）
│   ├── chapter_parser.py   # 章节自动切分
│   ├── tts_engine.py       # edge-tts 封装（音色/语速/MP3）
│   └── progress.py         # 断点续听进度管理
├── cli.py                  # 命令行工具（听书 + 生成 MP3）
├── web_app.py              # Web 网页版（Flask）
├── desktop_app.py          # 桌面 GUI（tkinter）
└── requirements.txt
```

## ⚙️ 配置说明

- **断点续听**：进度保存在 `~/.audiobook_player/progress.json`
- **Web 缓存**：生成的音频缓存在 `audio_cache/` 目录，重复播放无需重新生成
- **代理支持**：自动读取环境变量 `HTTPS_PROXY` / `HTTP_PROXY`

## ⚠️ 常见问题

**Q: edge-tts 连接失败 / 返回 403？**
A: 微软的 TTS 服务会屏蔽部分数据中心 IP。请在个人电脑（家庭宽带 IP）上使用，或配置可用的代理。

**Q: 没有声音？**
A: 桌面/命令行听书需要安装 `pygame`：`pip install pygame`。Web 版直接用浏览器播放，无需额外依赖。

**Q: PDF 提取乱码？**
A: 扫描版 PDF 无法提取文字，需要先用 OCR 转换。文字版 PDF 可正常提取。

**Q: 生成 MP3 很慢？**
A: 长文本会按段落分块生成。可使用 `--single` 合成整本，但耗时较长。
