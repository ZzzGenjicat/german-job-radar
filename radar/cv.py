"""Bounded local CV storage and text extraction."""
import io
import re
import uuid
import zipfile
from pathlib import Path

from docx import Document
from pypdf import PdfReader

MAX_BYTES=8*1024*1024
MAX_TEXT=50000
MAX_PAGES=20
MAX_UNCOMPRESSED=25*1024*1024


def _docx_safe(content):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names=archive.namelist()
            if '[Content_Types].xml' not in names or 'word/document.xml' not in names:return False
            if sum(x.file_size for x in archive.infolist())>MAX_UNCOMPRESSED:return False
            return not any(name.startswith(('/','\\')) or '..' in Path(name).parts for name in names)
    except (zipfile.BadZipFile,OSError):return False


def save_and_extract_cv(filename,content,data_dir):
    if not isinstance(filename,str) or not isinstance(content,(bytes,bytearray)):raise ValueError('简历文件无效')
    if not content or len(content)>MAX_BYTES:raise ValueError('简历文件必须小于 8 MB')
    suffix=Path(filename).suffix.casefold()
    if suffix not in ('.pdf','.docx'):raise ValueError('只支持 PDF 或 DOCX 简历')
    if suffix=='.pdf' and not bytes(content).startswith(b'%PDF-'):raise ValueError('文件内容与 PDF 扩展名不一致')
    if suffix=='.docx' and not _docx_safe(content):raise ValueError('DOCX 文件结构无效或过大')
    root=Path(data_dir).resolve();root.mkdir(parents=True,exist_ok=True)
    stored=uuid.uuid4().hex+suffix;path=(root/stored).resolve()
    if path.parent!=root:raise ValueError('简历保存路径无效')
    try:
        path.write_bytes(content)
        if suffix=='.pdf':
            reader=PdfReader(io.BytesIO(content),strict=False)
            if len(reader.pages)>MAX_PAGES:raise ValueError('PDF 页数超过 20 页')
            text='\n'.join((page.extract_text() or '') for page in reader.pages)
        else:
            document=Document(io.BytesIO(content))
            lines=[]
            for block in list(document.element.body)[:4000]:
                value=' '.join(node.text or '' for node in block.iter() if node.tag.endswith('}t')).strip()
                if value:lines.append(value)
            text='\n'.join(lines)
        text=re.sub(r'[ \t]+',' ',text);text=re.sub(r'\n{3,}','\n\n',text).strip()[:MAX_TEXT]
        if not text:raise ValueError('没有从简历中提取到文字，请换用可复制文字的 PDF 或 DOCX')
        return {'id':uuid.uuid4().hex,'original_name':Path(filename).name,'stored_name':stored,'kind':suffix[1:],'text':text,'chars':len(text)}
    except Exception as exc:
        path.unlink(missing_ok=True)
        if isinstance(exc,(ValueError,OSError)):raise
        raise ValueError('简历无法解析，请换用可复制文字的 PDF 或有效 DOCX') from None
