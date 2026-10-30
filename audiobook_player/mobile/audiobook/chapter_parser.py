"""章节解析模块：将长文本按章节标题切分"""
import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class Chapter:
    title: str
    content: str
    index: int = 0


# 常见章节标题模式（中文 + 英文）
CHAPTER_PATTERNS = [
    r"^第[一二三四五六七八九十百千零〇\d]+[章节回卷集部篇幕]",
    r"^第\s*\d+\s*[章节回卷集部篇幕]",
    r"^Chapter\s+\d+",
    r"^CHAPTER\s+\d+",
    r"^\d+\.\s+\S",
    r"^[一二三四五六七八九十百千]+、",
    r"^序[章节言]?\s*[:：]?",
    r"^楔子\s*[:：]?",
    r"^尾声\s*[:：]?",
    r"^番外(篇)?\s*[:：]?",
]


def parse_chapters(text: str, min_title_length: int = 2) -> List[Chapter]:
    """
    将文本按章节标题切分。
    如果没有匹配到章节标题，则把整篇作为一个章节。
    """
    lines = text.splitlines()
    chapters: List[Chapter] = []
    current_title = "正文"
    current_lines: List[str] = []

    combined = re.compile("|".join(CHAPTER_PATTERNS))

    for line in lines:
        stripped = line.strip()
        if stripped and combined.match(stripped) and len(stripped) <= 60:
            # 保存上一章
            if current_lines:
                chapters.append(Chapter(
                    title=current_title,
                    content="\n".join(current_lines).strip(),
                    index=len(chapters),
                ))
            current_title = stripped
            current_lines = []
        else:
            current_lines.append(line)

    # 最后一章
    if current_lines:
        chapters.append(Chapter(
            title=current_title,
            content="\n".join(current_lines).strip(),
            index=len(chapters),
        ))

    # 如果只有一章且标题是默认的，尝试用前几行做标题
    if len(chapters) == 1 and chapters[0].title == "正文":
        first_line = next((l.strip() for l in lines if l.strip()), "正文")
        if first_line:
            chapters[0].title = first_line[:40]

    return chapters


def split_long_text(text: str, max_chars: int = 2000) -> List[str]:
    """将过长的文本按段落切分成小块，避免 TTS 一次性处理过长"""
    if len(text) <= max_chars:
        return [text]

    # 按段落切
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: List[str] = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) + 1 <= max_chars:
            current = current + "\n" + p if current else p
        else:
            if current:
                chunks.append(current)
            # 单段过长则按句子切
            if len(p) > max_chars:
                sentences = re.split(r"(?<=[。！？.!?])", p)
                buf = ""
                for s in sentences:
                    if len(buf) + len(s) <= max_chars:
                        buf += s
                    else:
                        if buf:
                            chunks.append(buf)
                        buf = s
                if buf:
                    current = buf
                else:
                    current = ""
            else:
                current = p
    if current:
        chunks.append(current)
    return chunks
