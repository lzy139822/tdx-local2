"""Web 听书应用 - Flask 后端

功能：
- 上传电子书（TXT/EPUB/PDF）
- 章节列表展示与导航
- 在线播放章节音频（edge-tts 实时合成）
- 断点续听（localStorage + 服务端进度）
- 音色 / 语速切换
- 下载章节 MP3 或整本 MP3
"""
import asyncio
import os
import sys
import tempfile
import threading
import uuid
from typing import Dict

from flask import (Flask, request, jsonify, send_file, render_template_string,
                   Response, stream_with_context)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audiobook.text_extractor import extract_text
from audiobook.chapter_parser import parse_chapters
from audiobook.tts_engine import (
    get_voice_list, stream_to_file, generate_chapter_audio, _normalize_rate,
)
from audiobook.progress import save_progress, get_progress

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200MB

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "audio_cache")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# 内存中保存已解析的书（book_id -> {chapters, file_path}）
books: Dict[str, dict] = {}

# 音频生成锁（避免并发生成同一章）
audio_locks: Dict[str, threading.Lock] = {}


def _get_or_create_book(book_id: str):
    book = books.get(book_id)
    if book:
        return book
    # 从上传目录恢复
    for f in os.listdir(UPLOAD_DIR):
        if f.startswith(book_id + ".") or f.startswith(book_id + "_"):
            path = os.path.join(UPLOAD_DIR, f)
            text = extract_text(path)
            chapters = parse_chapters(text)
            books[book_id] = {"chapters": chapters, "file_path": path}
            return books[book_id]
    return None


@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/api/voices")
def api_voices():
    return jsonify([{"id": v[0], "name": v[1]} for v in get_voice_list()])


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "没有上传文件"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "文件名为空"}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in (".txt", ".epub", ".pdf"):
        return jsonify({"error": f"不支持格式 {ext}"}), 400

    book_id = uuid.uuid4().hex[:12]
    save_name = f"{book_id}_{f.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)
    f.save(save_path)

    try:
        text = extract_text(save_path)
        chapters = parse_chapters(text)
    except Exception as e:
        os.remove(save_path)
        return jsonify({"error": f"解析失败: {e}"}), 500

    books[book_id] = {"chapters": chapters, "file_path": save_path}
    return jsonify({
        "book_id": book_id,
        "filename": f.filename,
        "chapters": [
            {"index": c.index, "title": c.title, "length": len(c.content)}
            for c in chapters
        ],
    })


@app.route("/api/book/<book_id>")
def api_book(book_id):
    book = _get_or_create_book(book_id)
    if not book:
        return jsonify({"error": "书籍不存在"}), 404
    return jsonify({
        "book_id": book_id,
        "chapters": [
            {"index": c.index, "title": c.title, "length": len(c.content)}
            for c in book["chapters"]
        ],
    })


@app.route("/api/progress/<book_id>")
def api_get_progress(book_id):
    book = _get_or_create_book(book_id)
    if not book:
        return jsonify({})
    prog = get_progress(book["file_path"])
    return jsonify(prog or {})


@app.route("/api/progress/<book_id>", methods=["POST"])
def api_save_progress(book_id):
    book = _get_or_create_book(book_id)
    if not book:
        return jsonify({"error": "书籍不存在"}), 404
    data = request.get_json() or {}
    save_progress(
        book["file_path"],
        data.get("chapter", 0),
        data.get("position", 0.0),
        data.get("voice", ""),
        data.get("rate", ""),
    )
    return jsonify({"ok": True})


def _audio_cache_path(book_id: str, chapter_idx: int, voice: str, rate: str) -> str:
    rate_safe = rate.replace("+", "p").replace("-", "m").replace("%", "")
    return os.path.join(CACHE_DIR, f"{book_id}_{chapter_idx}_{voice}_{rate_safe}.mp3")


@app.route("/api/audio/<book_id>/<int:chapter_idx>")
def api_audio(book_id, chapter_idx):
    """生成并返回章节音频。支持 ?voice=&rate= 参数，已生成的会缓存。"""
    book = _get_or_create_book(book_id)
    if not book or chapter_idx >= len(book["chapters"]):
        return jsonify({"error": "章节不存在"}), 404

    voice = request.args.get("voice", "zh-CN-XiaoxiaoNeural")
    rate = _normalize_rate(request.args.get("rate", "1.0"))
    cache_path = _audio_cache_path(book_id, chapter_idx, voice, rate)

    lock_key = cache_path
    lock = audio_locks.setdefault(lock_key, threading.Lock())

    def generate():
        with lock:
            if not os.path.exists(cache_path):
                chapter = book["chapters"][chapter_idx]
                asyncio.run(generate_chapter_audio(
                    chapter.content, cache_path, voice, rate
                ))
        # 流式返回文件
        with open(cache_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                yield chunk

    return Response(
        stream_with_context(generate()),
        mimetype="audio/mpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.route("/api/download/<book_id>/<int:chapter_idx>")
def api_download(book_id, chapter_idx):
    book = _get_or_create_book(book_id)
    if not book or chapter_idx >= len(book["chapters"]):
        return jsonify({"error": "章节不存在"}), 404
    voice = request.args.get("voice", "zh-CN-XiaoxiaoNeural")
    rate = _normalize_rate(request.args.get("rate", "1.0"))
    cache_path = _audio_cache_path(book_id, chapter_idx, voice, rate)
    if not os.path.exists(cache_path):
        chapter = book["chapters"][chapter_idx]
        asyncio.run(generate_chapter_audio(chapter.content, cache_path, voice, rate))
    chapter = book["chapters"][chapter_idx]
    return send_file(cache_path, as_attachment=True,
                     download_name=f"{chapter_idx+1:04d}_{chapter.title[:30]}.mp3")


INDEX_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📚 听书 - 电子书语音朗读</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
         min-height: 100vh; color: #333; }
  .container { max-width: 960px; margin: 0 auto; padding: 20px; }
  h1 { color: #fff; text-align: center; padding: 30px 0 10px; font-size: 2em; text-shadow: 0 2px 4px rgba(0,0,0,.2);}
  .card { background: #fff; border-radius: 16px; padding: 24px; margin: 16px 0;
          box-shadow: 0 8px 32px rgba(0,0,0,.1); }
  .upload-area { border: 2px dashed #c5cae9; border-radius: 12px; padding: 40px;
                 text-align: center; cursor: pointer; transition: .2s; }
  .upload-area:hover { border-color: #667eea; background: #f5f7ff; }
  .upload-area input { display: none; }
  .controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
  select, input[type=range] { padding: 8px 12px; border: 1px solid #ddd;
           border-radius: 8px; font-size: 14px; }
  button { padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer;
           font-size: 14px; font-weight: 600; transition: .2s; }
  .btn-primary { background: #667eea; color: #fff; }
  .btn-primary:hover { background: #5568d3; }
  .btn-secondary { background: #f0f0f0; color: #555; }
  .btn-secondary:hover { background: #e0e0e0; }
  .chapter-list { max-height: 400px; overflow-y: auto; }
  .chapter-item { padding: 12px 16px; border-bottom: 1px solid #eee;
                  cursor: pointer; display: flex; justify-content: space-between;
                  align-items: center; transition: .15s; }
  .chapter-item:hover { background: #f5f7ff; }
  .chapter-item.active { background: #e8ecff; color: #667eea; font-weight: 600;
                          border-left: 3px solid #667eea; }
  .player { position: sticky; bottom: 0; background: #fff; border-radius: 16px;
            padding: 16px; margin-top: 16px; box-shadow: 0 -4px 20px rgba(0,0,0,.1);}
  audio { width: 100%; margin: 10px 0; }
  .info { color: #888; font-size: 13px; }
  .title { font-weight: 600; margin-bottom: 12px; font-size: 16px; }
</style>
</head>
<body>
<div class="container">
  <h1>📚 智能听书</h1>

  <div class="card">
    <div class="title">上传电子书</div>
    <label class="upload-area">
      <input type="file" id="fileInput" accept=".txt,.epub,.pdf">
      <div style="font-size:18px;color:#667eea;font-weight:600;">点击或拖拽上传</div>
      <div class="info" style="margin-top:8px;">支持 TXT / EPUB / PDF</div>
    </label>
  </div>

  <div class="card" id="bookCard" style="display:none;">
    <div class="title" id="bookTitle">书籍</div>
    <div class="controls" style="margin-bottom:16px;">
      <select id="voiceSelect"></select>
      <span style="font-size:13px;">语速:</span>
      <input type="range" id="rateSlider" min="0.5" max="2" step="0.1" value="1" style="width:120px;">
      <span id="rateLabel" style="font-size:13px;">1.0x</span>
      <button class="btn-primary" onclick="downloadChapter()">下载本章 MP3</button>
    </div>
    <div class="chapter-list" id="chapterList"></div>
  </div>

  <div class="player" id="player" style="display:none;">
    <div class="title" id="nowPlaying">正在播放</div>
    <audio id="audioPlayer" controls></audio>
    <div class="controls">
      <button class="btn-secondary" onclick="prevChapter()">⏮ 上一章</button>
      <button class="btn-secondary" onclick="nextChapter()">下一章 ⏭</button>
      <span class="info" id="playInfo"></span>
    </div>
  </div>
</div>

<script>
let bookId = null;
let chapters = [];
let currentIdx = 0;
let voices = [];

// 加载音色
fetch('/api/voices').then(r=>r.json()).then(data=>{
  voices = data;
  const sel = document.getElementById('voiceSelect');
  data.forEach(v=>{
    const o = document.createElement('option');
    o.value = v.id; o.textContent = v.name;
    sel.appendChild(o);
  });
  // 恢复上次音色
  const saved = localStorage.getItem('voice');
  if (saved) sel.value = saved;
  sel.onchange = ()=>{ localStorage.setItem('voice', sel.value); reloadAudio(); };
});

// 语速
const rateSlider = document.getElementById('rateSlider');
rateSlider.oninput = ()=>{
  document.getElementById('rateLabel').textContent = rateSlider.value + 'x';
  localStorage.setItem('rate', rateSlider.value);
  reloadAudio();
};
const savedRate = localStorage.getItem('rate');
if (savedRate){ rateSlider.value = savedRate; document.getElementById('rateLabel').textContent = savedRate+'x'; }

// 上传
document.getElementById('fileInput').onchange = async e=>{
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  document.getElementById('bookTitle').textContent = '正在解析...';
  document.getElementById('bookCard').style.display = 'block';
  try {
    const res = await fetch('/api/upload', {method:'POST', body: fd});
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    bookId = data.book_id;
    chapters = data.chapters;
    document.getElementById('bookTitle').textContent = data.filename;
    renderChapters();
    // 恢复进度
    const prog = await fetch('/api/progress/'+bookId).then(r=>r.json());
    if (prog.chapter != null) {
      currentIdx = prog.chapter;
      setTimeout(()=>playChapter(currentIdx), 500);
    }
  } catch(err) { alert('上传失败: '+err); }
};

function renderChapters(){
  const list = document.getElementById('chapterList');
  list.innerHTML = '';
  chapters.forEach(c=>{
    const div = document.createElement('div');
    div.className = 'chapter-item' + (c.index===currentIdx?' active':'');
    div.innerHTML = `<span>${c.index+1}. ${c.title}</span>
                     <span class="info">${Math.round(c.length/100)/10}k 字</span>`;
    div.onclick = ()=>playChapter(c.index);
    list.appendChild(div);
  });
}

function getVoice(){ return document.getElementById('voiceSelect').value; }
function getRate(){ return rateSlider.value; }

function audioUrl(idx){
  return `/api/audio/${bookId}/${idx}?voice=${getVoice()}&rate=${getRate()}`;
}

function playChapter(idx){
  if (idx < 0 || idx >= chapters.length) return;
  currentIdx = idx;
  renderChapters();
  const ch = chapters[idx];
  document.getElementById('nowPlaying').textContent = `正在播放：${ch.title}`;
  const audio = document.getElementById('audioPlayer');
  audio.src = audioUrl(idx);
  audio.play();
  document.getElementById('player').style.display = 'block';
  document.getElementById('playInfo').textContent = `${idx+1} / ${chapters.length}`;
  // 保存进度
  fetch('/api/progress/'+bookId, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({chapter: idx, voice: getVoice(), rate: getRate()})
  });
}

function reloadAudio(){
  if (bookId == null) return;
  const audio = document.getElementById('audioPlayer');
  const wasPlaying = !audio.paused;
  audio.src = audioUrl(currentIdx);
  if (wasPlaying) audio.play();
}

function prevChapter(){ if (currentIdx>0) playChapter(currentIdx-1); }
function nextChapter(){ if (currentIdx<chapters.length-1) playChapter(currentIdx+1); }

document.getElementById('audioPlayer').onended = nextChapter;

function downloadChapter(){
  if (bookId==null) return;
  window.open(`/api/download/${bookId}/${currentIdx}?voice=${getVoice()}&rate=${getRate()}`);
}
</script>
</body>
</html>
"""


def main():
    import argparse
    p = argparse.ArgumentParser(description="Web 听书应用")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()
    print(f"🌐 听书 Web 应用启动: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
