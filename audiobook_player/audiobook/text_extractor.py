"""文本提取模块：支持 TXT / EPUB / PDF"""
import os
import re
from typing import List


def extract_text(file_path: str) -> str:
    """根据文件扩展名自动选择提取方式"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".txt":
        return _extract_txt(file_path)
    elif ext == ".epub":
        return _extract_epub(file_path)
    elif ext == ".pdf":
        return _extract_pdf(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}（支持 .txt / .epub / .pdf）")


def _extract_txt(file_path: str) -> str:
    """读取 TXT 文件，自动尝试常见编码"""
    encodings = ["utf-8", "gbk", "gb18030", "utf-16", "latin-1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    # 最后兜底：忽略错误
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _extract_epub(file_path: str) -> str:
    """提取 EPUB 文本"""
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("读取 EPUB 需要安装依赖: pip install ebooklib beautifulsoup4")

    book = epub.read_epub(file_path)
    parts: List[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n")
        parts.append(text)
    return "\n".join(parts)


def _extract_pdf(file_path: str) -> str:
    """提取 PDF 文本"""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("读取 PDF 需要安装依赖: pip install pdfplumber")

    parts: List[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            parts.append(text)
    return "\n".join(parts)
