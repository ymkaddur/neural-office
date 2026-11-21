"""Read-only, bounded previews for text, Office packages, media and opaque files."""
from io import BytesIO
from pathlib import PurePosixPath
import re
import wave
import xml.etree.ElementTree as ET
import zipfile

TEXT_SUFFIXES = set(('.txt .md .mdx .rst .csv .tsv .log .xml .svg .yml .yaml .toml .ini '
                     '.cfg .conf .py .rs .js .ts .jsx .tsx .css .sql .c .cpp .h .java '
                     '.cs .go .sh .ps1 .bat .diff .patch .srt .vtt .jsonl .ndjson').split())
OFFICE = {'.docx':'docx', '.pptx':'pptx', '.xlsx':'xlsx', '.odt':'odt', '.ods':'ods', '.odp':'odp'}
EXTRA_IMAGES = {'gif':'GIF','webp':'WEBP','bmp':'BMP','tiff':'TIFF'}


def detect(name, header, legacy):
    suffix = PurePosixPath(name).suffix.lower()
    if legacy == 'zip':
        return OFFICE.get(suffix, 'zip')
    if legacy != 'other':
        return legacy
    if header.startswith((b'GIF87a', b'GIF89a')):
        return 'gif'
    if header.startswith(b'RIFF') and header[8:12] in (b'WEBP', b'WAVE'):
        return 'webp' if header[8:12] == b'WEBP' else 'wav'
    if header.startswith((b'II*\x00', b'MM\x00*')):
        return 'tiff'
    if header.startswith(b'BM'):
        return 'bmp'
    if header[4:8] == b'ftyp':
        return 'isobmff'
    return 'text' if suffix in TEXT_SUFFIXES else 'other'


def plain(data):
    try:
        enc = 'utf-32' if data.startswith((b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff')) else (
              'utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
        text = data.decode(enc)
    except UnicodeError:
        return None
    if any(ord(c)<32 and c not in '\r\n\t\f' for c in text):
        return None
    return text


def xml_syntax(data):
    if len(data) > 1024 * 1024:
        return dict(xml_detail='El lector de sintaxis XML admite hasta 1 MiB.')
    text = plain(data)
    if text is None or re.search(r'<!\s*(?:DOCTYPE|ENTITY)', text, re.I):
        return dict(xml_detail='La codificación o la declaración del documento requiere otro lector XML.')
    try:
        ET.fromstring(text)
    except ET.ParseError as exc:
        line, column = exc.position
        return dict(xml_valid=False, line=line, column=column+1,
                    xml_detail=f'El XML contiene un error en la línea {line}, columna {column+1}.')
    return dict(xml_valid=True, xml_detail='El documento XML está bien formado.')


def xml_part(archive, info):
    if info.file_size > 1024*1024 or info.flag_bits & 1 or info.compress_type not in (0, 8) or info.file_size > 200*max(1,info.compress_size):
        raise ValueError('part limit')
    with archive.open(info) as stream:
        data=stream.read(1024*1024+1)
    if len(data)!=info.file_size:
        raise ValueError('incomplete part')
    text=plain(data)
    if text is None or re.search(r'<!\s*(?:DOCTYPE|ENTITY)',text,re.I):
        raise ValueError('unsupported XML')
    root=ET.fromstring(text)
    if sum(1 for _ in root.iter())>40000:
        raise ValueError('XML limit')
    return root


def office_text(kind, data):
    from .attachment_formats import zip_view, result, MAX_TEXT
    inventory=zip_view(data,1,'','inspect')
    if inventory['status']!='ok':
        return result(kind,inventory['status'],inventory['detail'])
    with zipfile.ZipFile(BytesIO(data)) as archive:
        names=archive.namelist()
        pattern={'docx':r'word/document\.xml', 'pptx':r'ppt/slides/slide[1-9]\d*\.xml',
                 'xlsx':r'xl/worksheets/sheet[1-9]\d*\.xml'}.get(kind,r'content\.xml')
        parts=sorted([n for n in names if re.fullmatch(pattern,n)],key=lambda x:int((re.search(r'(\d+)\.xml$',x) or [None,0])[1]))
        if not parts or len(parts)!=len(set(parts)):
            return result(kind,'invalid','El paquete no contiene las partes de documento esperadas.')
        selected=parts[:24]
        has_shared=kind=='xlsx' and 'xl/sharedStrings.xml' in names
        required=selected+(['xl/sharedStrings.xml'] if has_shared else [])
        if any(names.count(n)!=1 for n in required) or sum(archive.getinfo(n).file_size for n in required)>4*1024*1024:
            return result(kind,'limit','Las partes del documento superan el presupuesto de lectura.')
        shared=[]
        if has_shared:
            shared=[''.join(t.text or '' for t in si.findall('.//{*}t')) for si in xml_part(archive,archive.getinfo('xl/sharedStrings.xml')).findall('{*}si')]
        lines=[]
        for part in selected:
            root=xml_part(archive,archive.getinfo(part))
            if kind=='xlsx':
                for cell in root.findall('.//{*}sheetData/{*}row/{*}c'):
                    cached = cell.find('{*}v')
                    value = (cached.text or '') if cached is not None else ''
                    formula = cell.find('{*}f')
                    if formula is not None and (cached is None or (not value and cell.get('t') != 'str')):
                        expression = '=' + formula.text if formula.text else 'Fórmula'
                        value = expression + ' · sin resultado guardado'
                    elif cell.get('t')=='s':
                        if not value.isdecimal() or int(value)>=len(shared):
                            raise ValueError('shared string index')
                        value=shared[int(value)]
                    elif cell.get('t')=='inlineStr':
                        value=''.join(t.text or '' for t in cell.findall('.//{*}t'))
                    lines.append(part.split('/')[-1]+' · '+(cell.get('r') or '?')+'  '+value)
            elif kind in ('odt','ods','odp'):
                lines.extend(''.join(p.itertext()) for p in root.iter() if p.tag.rsplit('}',1)[-1] in ('h','p'))
            elif kind == 'docx':
                separators = {'tab': '\t', 'br': '\n', 'cr': '\n'}
                for paragraph in root.findall('.//{*}p'):
                    fragments = []
                    for node in paragraph.iter():
                        tag = node.tag.rsplit('}', 1)[-1]
                        if tag == 't':
                            fragments.append(node.text or '')
                        elif tag in separators:
                            fragments.append(separators[tag])
                    lines.append(''.join(fragments))
            else:
                lines.extend(''.join(t.text or '' for t in p.findall('.//{*}t')) for p in root.findall('.//{*}p'))
        text='\n'.join(lines)
        return result(kind,'ok','Texto recuperado de las partes del documento.',text=text[:MAX_TEXT],
                      text_truncated=len(text)>MAX_TEXT or len(parts)>len(selected),parts=len(selected))


def general_view(kind, data):
    from .attachment_formats import result, MAX_TEXT
    if kind in OFFICE.values():
        return office_text(kind,data)
    if kind=='wav':
        with wave.open(BytesIO(data),'rb') as audio:
            rate = audio.getframerate()
            frames = audio.getnframes()
            frame_bytes = audio.getnchannels() * audio.getsampwidth()
            if rate <= 0 or frames * frame_bytes > len(data):
                raise ValueError('invalid PCM header')
            remaining = frames
            while remaining:
                block = min(remaining, max(1, 65536 // frame_bytes))
                if len(audio.readframes(block)) != block * frame_bytes:
                    raise ValueError('truncated PCM data')
                remaining -= block
            return result(kind, 'ok', f'{audio.getnchannels()} canales · {rate} Hz · {frames/rate:.2f} s.', bytes=len(data))
    text=plain(data) if kind in ('text','other') else None
    if text is not None:
        return result(kind,'ok','Texto local de solo lectura.',text=text[:MAX_TEXT],text_truncated=len(text)>MAX_TEXT,
                      total_lines=len(text.splitlines()),text_start_line=1)
    return result(kind,'metadata','Se identificaron los bytes y su huella. El contenido no tiene lector disponible.',
                  bytes=len(data),signature=data[:32].hex(' '))
