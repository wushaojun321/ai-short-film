"""Extract plain script text from uploaded files."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET


class ScriptTextExtractionError(ValueError):
    """Raised when an uploaded script file cannot be converted to text."""


def _decode_text(content: bytes) -> str:
    encodings = ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5")
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ScriptTextExtractionError("无法读取文本文件，请上传 UTF-8、GBK 或 GB18030 编码的 .txt 文件")


def _extract_docx(content: bytes) -> str:
    try:
        with ZipFile(BytesIO(content)) as docx:
            xml_bytes = docx.read("word/document.xml")
    except (BadZipFile, KeyError):
        raise ScriptTextExtractionError("无法读取 .docx 文件，请确认文件不是损坏的 Word 文档")

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        raise ScriptTextExtractionError("无法解析 .docx 正文内容，请重新导出后上传")

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        parts = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ScriptTextExtractionError("服务器暂未安装 PDF 文本解析依赖，请先上传 .txt 或 .docx 文件") from exc

    try:
        reader = PdfReader(BytesIO(content))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise ScriptTextExtractionError("无法读取 PDF 文件，请确认 PDF 未损坏且包含可复制文本") from exc

    return "\n\n".join(page for page in pages if page)


def extract_script_text(filename: str, content: bytes, content_type: str | None = None) -> str:
    """Extract plain text from txt/docx/pdf uploads."""
    suffix = Path(filename or "").suffix.lower()
    mime = (content_type or "").lower()

    if suffix == ".txt" or mime.startswith("text/"):
        text = _decode_text(content)
    elif suffix == ".docx" or mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = _extract_docx(content)
    elif suffix == ".pdf" or mime == "application/pdf":
        text = _extract_pdf(content)
    else:
        raise ScriptTextExtractionError("仅支持上传 .txt、.docx 或 .pdf 剧本文件")

    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ScriptTextExtractionError("未能从文件中提取到剧本文本，请检查文件内容是否为空或是否为扫描版 PDF")
    return text
