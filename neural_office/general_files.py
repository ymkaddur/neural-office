"""Read-only, bounded previews for text, Office packages, media and opaque files."""
from io import BytesIO
from pathlib import PurePosixPath
import re
import posixpath
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


def presentation_order(archive, names, slides):
    presentation = 'ppt/presentation.xml'
    relationships = 'ppt/_rels/presentation.xml.rels'
    if presentation not in names and relationships not in names:
        return slides, False
    if any(names.count(n) != 1 for n in (presentation, relationships)):
        raise ValueError('incomplete slide order')
    roots = [xml_part(archive, archive.getinfo(n)) for n in (presentation, relationships)]
    targets = {}
    for relation in roots[1].findall('{*}Relationship'):
        if relation.get('TargetMode') == 'External' or not relation.get('Type', '').endswith('/slide'):
            continue
        target = relation.get('Target', '')
        path = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('ppt', target))
        link = relation.get('Id')
        if not link or link in targets or path not in slides:
            raise ValueError('invalid slide relationship')
        targets[link] = path
    refs = roots[0].find('{*}sldIdLst')
    if refs is None:
        raise ValueError('missing slide references')
    ordered = []
    for ref in refs.findall('{*}sldId'):
        links = [value for key, value in ref.attrib.items() if key.endswith('}id')]
        if len(links) != 1 or links[0] not in targets or targets[links[0]] in ordered:
            raise ValueError('unresolved slide reference')
        ordered.append(targets[links[0]])
    return ordered, True


def word_paragraphs(root):
    lines, fragments = [], []
    def finish():
        lines.append(''.join(fragments))
        fragments.clear()
    def visit(element, in_paragraph):
        tag = element.tag.rsplit('}', 1)[-1]
        if tag == 'p':
            if fragments:
                finish()
            start = len(lines)
            for child in element:
                visit(child,True)
            if fragments or start==len(lines):
                finish()
        elif in_paragraph and tag == 't':
            fragments.append(element.text or '')
        elif in_paragraph and tag in ('tab','br','cr'):
            fragments.append('\t' if tag=='tab' else '\n')
        else:
            for child in element:
                visit(child,in_paragraph)
    visit(root,False)
    return lines


def odf_text(root, maximum):
    text_ns = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'
    office = '{urn:oasis:names:tc:opendocument:xmlns:office:1.0}'
    cell = '{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-cell'
    paragraphs = (text_ns+'p', text_ns+'h', 'p', 'h')
    fragments = []
    size = 0
    def append(value):
        nonlocal size
        text = (value or '')[:maximum + 1 - size]
        fragments.append(text)
        size += len(text)
    def content(node):
        append(node.text)
        for child in node:
            if size > maximum:
                return
            if child.tag == text_ns+'s':
                qty = child.get(text_ns+'c', '1')
                if not qty.isascii() or not qty.isdecimal() or len(qty) > 9 or int(qty) < 1:
                    raise ValueError('invalid ODF space count')
                append(' ' * min(int(qty), maximum + 1 - size))
            elif child.tag in (text_ns+'tab', text_ns+'line-break'):
                append('\t' if child.tag == text_ns+'tab' else '\n')
            else:
                content(child)
            append(child.tail)
    blocks = 0
    for element in root.iter():
        if size > maximum:
            break
        if element.tag in paragraphs:
            if blocks: append('\n')
            content(element)
            blocks += 1
        elif element.tag == cell and not any(p.tag in paragraphs for p in element.iter()):
            fallback = next((element.get(office+key) for key in ('value','date-value','time-value','boolean-value','string-value') if office+key in element.attrib), None)
            if fallback is not None:
                if blocks: append('\n')
                append(fallback)
                blocks += 1
    return ''.join(fragments)


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
        known_order=True
        if kind=='pptx':
            parts,known_order=presentation_order(archive,names,parts)
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
                lines.append(odf_text(root, MAX_TEXT))
            elif kind == 'docx':
                lines.extend(word_paragraphs(root))
            else:
                lines.extend(''.join(t.text or '' for t in p.findall('.//{*}t')) for p in root.findall('.//{*}p'))
        text='\n'.join(lines)
        detail = ('Texto recuperado de las partes del documento.' if known_order else
                  'Texto recuperado por partes. El paquete no declara el orden de las diapositivas.')
        return result(kind,'ok',detail,text=text[:MAX_TEXT],
                      text_truncated=len(text)>MAX_TEXT or len(parts)>len(selected) or not known_order,parts=len(selected))


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
