# 📱 听书 App - Android 打包指南

将听书程序打包为 Android APK，可直接安装到手机使用。

## 📦 工程结构

```
mobile/
├── main.py              # Kivy 应用入口（UI + 业务逻辑）
├── buildozer.spec       # Buildozer 打包配置
└── audiobook/           # 核心模块（文本提取、章节解析、TTS、进度）
    ├── text_extractor.py
    ├── chapter_parser.py
    ├── tts_engine.py
    └── progress.py
```

## 🛠️ 打包环境要求

打包必须在 **Linux** 环境进行（Windows 用户请用 WSL2）。

### 方案 A：Linux / WSL2（推荐）

#### 1. 安装系统依赖

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev \
    ccache automake

# 安装 Buildozer
pip install --user buildozer
```

#### 2. 进入工程目录

```bash
cd audiobook_player/mobile
```

#### 3. 开始打包

```bash
buildozer -v android debug
```

首次打包会自动下载 Android SDK、NDK、Python for Android 工具链，耗时约 20-40 分钟（取决于网络）。后续打包会快很多。

#### 4. 获取 APK

打包成功后，APK 在：
```
bin/audiobook-1.0.0-arm64-v8a_armeabi-v7a-debug.apk
```

#### 5. 安装到手机

```bash
# 方式一：adb 安装（需开启 USB 调试）
adb install bin/audiobook-1.0.0-arm64-v8a_armeabi-v7a-debug.apk

# 方式二：将 APK 传到手机，点击安装
```

### 方案 B：Docker 打包（无需配置环境）

```bash
# 使用官方 Buildozer Docker 镜像
docker run --rm -v "$(pwd)":/home/user/gradle \
    -v buildozer_data:/home/user/.buildozer \
    kivy/buildozer android debug
```

## ⚙️ 配置说明

### 修改应用信息

编辑 `buildozer.spec`：

```ini
title = 听书                          # 应用名称
package.name = audiobook              # 包名
package.domain = org.audiobook        # 包域名
version = 1.0.0                       # 版本号
```

### 添加应用图标

将 512x512 的 PNG 图标命名为 `icon.png` 放在 `mobile/` 目录，然后在 `buildozer.spec` 中取消注释：

```ini
icon.filename = %(source.dir)s/icon.png
```

### 权限说明

已在 `buildozer.spec` 中配置：
- `INTERNET` - edge-tts 在线语音合成需要
- `READ_EXTERNAL_STORAGE` - 读取电子书文件
- `WRITE_EXTERNAL_STORAGE` - 保存 MP3 到下载目录

Android 11+ 首次打开应用时，会弹窗请求存储权限，请允许。

## 🚀 使用说明

1. 打开「听书」App
2. 点击「📂 打开电子书」，选择 TXT / EPUB / PDF 文件
3. 自动解析章节，显示章节列表
4. 选择音色（默认晓晓）和语速（0.5x ~ 2.0x）
5. 点击章节或「▶」按钮开始播放
6. 播放控制：⏮ 上一章 / ▶ 播放 / ⏸ 暂停 / ⏹ 停止 / ⏭ 下一章
7. 点击「💾」将当前章节导出为 MP3（保存到 Download 目录）
8. **断点续听**：自动记住上次听到的章节，下次打开同一本书可继续

## ⚠️ 常见问题

**Q: 打包时报错 `ModuleNotFoundError: No module named 'xxx'`？**
A: 在 `buildozer.spec` 的 `requirements` 中添加缺失的模块名。

**Q: 打包失败提示 NDK/SDK 问题？**
A: 删除 `.buildozer` 目录重新打包，Buildozer 会自动下载正确版本。

**Q: 安装 APK 时提示「解析包错误」？**
A: 检查手机 CPU 架构是否在 `android.archs` 配置中。现代手机都是 arm64-v8a。

**Q: PDF 文件无法打开？**
A: PDF 解析依赖 Pillow，首次打包若 Pillow 编译失败，可暂时从 requirements 中移除 `pdfplumber` 和 `pillow`，仅使用 TXT/EPUB。

**Q: 没有声音？**
A: 检查手机媒体音量；edge-tts 需要联网，确保网络正常。

**Q: 生成音频很慢？**
A: edge-tts 是在线合成，速度取决于网络。建议在 Wi-Fi 下使用。

## 📝 备注

- iOS 不支持（Buildozer 仅支持 Android）
- 上架应用商店需要签名 APK 和合规审核
- edge-tts 音色来自微软，免费但需联网
