"""Bounded, read-only inspectors for captured bytes. Their output may cross IPC."""
import base64
from bisect import bisect_right
from contextlib import closing
from decimal import Decimal
from io import BytesIO
import json
import math
from pathlib import PurePosixPath
import re
import stat
import struct
import unicodedata
import wave
import zipfile

from .audit import audit_html


MIB = 1024 * 1024
MAX_FILE = 8 * MIB
MAX_TEXT = 16_000
MAX_FIELDS = 160
MAX_PAGES = 40
MAX_MEMBER = 4 * MIB
MAX_ENTRIES = 160
MAX_PIXELS = 12_000_000
EXTENSIONS = {'.pdf': 'pdf', '.json': 'json', '.zip': 'zip', '.png': 'png',
              '.jpg': 'jpeg', '.jpeg': 'jpeg', '.html': 'html', '.htm': 'html'}


def legacy_kind(name, data):
    for signature, kind in ((b'%PDF-', 'pdf'), (b'PK\x03\x04', 'zip'),
                            (b'PK\x05\x06', 'zip'), (b'\x89PNG\r\n\x1a\n', 'png'),
                            (b'\xff\xd8\xff', 'jpeg')):
        if data.startswith(signature):
            return kind
    return EXTENSIONS.get(PurePosixPath(name).suffix.lower(), 'other')


def classify(name, data):
    from .general_files import detect
    return detect(name, data[:16], legacy_kind(name, data))


def result(kind, status, detail, **values):
    return dict(kind=kind, status=status, detail=detail, **values)


def raster(image):
    from PIL import Image
    image.thumbnail((900, 1000), Image.Resampling.LANCZOS)
    if image.mode != 'RGB':
        rgba = image.convert('RGBA')
        image = Image.new('RGB', rgba.size, 'white')
        image.paste(rgba, mask=rgba.getchannel('A'))
    for quality in (86, 65, 46, 32):
        output = BytesIO()
        image.save(output, format='JPEG', quality=quality)
        if output.tell() <= 100 * 1024:
            return 'data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode('ascii')
        image.thumbnail((max(1, image.width * 4 // 5), max(1, image.height * 4 // 5)))
    raise ValueError('RASTER_SIZE')


def image_view(kind, data, mode):
    from PIL import Image, ImageOps
    from .general_files import EXTRA_IMAGES
    formats = {'jpeg': 'JPEG', 'png': 'PNG', **EXTRA_IMAGES}
    try:
        opened = Image.open(BytesIO(data), formats=(formats[kind],))
    except Image.DecompressionBombError:
        return result(kind, 'limit', 'La imagen supera los 12 megapíxeles admitidos.')
    with opened as image:
        if image.format != formats[kind]:
            return result(kind, 'invalid', 'La cabecera y el formato de la imagen no coinciden.')
        width, height = image.size
        if width * height > MAX_PIXELS:
            return result(kind, 'limit', 'La imagen supera los 12 megapíxeles admitidos.')
        orientation = image.getexif().get(274, 1)
        image.load()  # verify pixel decoding even for an inspection without preview
        orientation = orientation if orientation in range(1, 9) else 1
        displayed_width, displayed_height = (height, width) if orientation >= 5 else (width, height)
        values = dict(width=displayed_width, height=displayed_height, original_width=width,
                      original_height=height, orientation=orientation)
        if mode == 'preview':
            with ImageOps.exif_transpose(image) as frame:
                values['image'] = raster(frame)
        return result(kind, 'ok', 'Vista de la primera imagen, con su orientación de lectura.', **values)


class JsonLocationError(ValueError):
    def __init__(self, detail, at):
        super().__init__(detail)
        self.at = at


def json_view(data):
    if len(data) > MIB:
        return result('json', 'limit', 'El lector JSON admite hasta 1 MiB por archivo.')
    source = data.decode('utf-8-sig', errors='strict')
    # Tell CRLF, CR and LF lines apart while keeping source offsets exact.
    starts = [0] + [m.end() for m in re.finditer(r'\r\n|\r|\n', source)]
    white = re.compile(r'[ \t\r\n]*')
    decoder = json.JSONDecoder(parse_float=Decimal)
    fields = []
    nodes = 0
    schema = None
    hours = None

    def skip(at):
        return white.match(source, at).end()

    def parse(at, pointer, depth):
        nonlocal nodes, hours, schema
        nodes += 1
        if depth > 40 or nodes > 10_000 or len(pointer) > 1400:
            raise JsonLocationError('La estructura excede el límite de lectura.', at)
        at = skip(at)
        char = source[at:at + 1]
        line = bisect_right(starts, at)
        if char in ('{', '['):
            is_object = char == '{'
            end = '}' if is_object else ']'
            i = skip(at + 1)
            keys = set()
            index = 0
            if source[i:i + 1] == end:
                return i + 1
            while True:
                if is_object:
                    key_start = i
                    if source[i:i + 1] != '"':
                        raise JsonLocationError('Se esperaba una clave JSON entre comillas.', i)
                    key, i = decoder.raw_decode(source, i)
                    if any(0xd800 <= ord(c) <= 0xdfff for c in key):
                        raise JsonLocationError('La clave contiene un carácter Unicode incompleto.', key_start)
                    if len(key) > 512:
                        raise JsonLocationError('La clave supera el límite de longitud.', key_start)
                    if key in keys:
                        raise JsonLocationError('Clave duplicada; corrígela antes de comparar.', key_start)
                    keys.add(key)
                    i = skip(i)
                    if source[i:i + 1] != ':':
                        raise JsonLocationError('Se esperaba el separador de un campo.', i)
                    i += 1
                    key = key.replace('~', '~0').replace('/', '~1')
                else:
                    key = str(index)
                i = skip(parse(i, pointer + '/' + key, depth + 1))
                if source[i:i + 1] == end:
                    return i + 1
                if source[i:i + 1] != ',':
                    raise JsonLocationError('Falta una coma o el cierre de la estructura.', i)
                i = skip(i + 1)
                index += 1
        value, end = decoder.raw_decode(source, at)
        if isinstance(value, float) and not math.isfinite(value):
            raise JsonLocationError('Se esperaba un número JSON finito.', at)
        if isinstance(value, Decimal):
            display = str(value)[:120]
        elif isinstance(value, str):
            if any(0xd800 <= ord(c) <= 0xdfff for c in value):
                raise JsonLocationError('El texto contiene un carácter Unicode incompleto.', at)
            display = value[:240]
        else:
            display = value
        field = dict(pointer=pointer, line=line, column=at - starts[line-1] + 1,
                     value=display, quote=source[at:end][:240])
        if len(fields) < MAX_FIELDS:
            fields.append(field)
        if pointer == '/response_sla_hours':
            hours = field if type(value) is int and 0 < value <= 1_000_000 else None
        elif pointer == '/$schema' and isinstance(value, str):
            schema = value[:300]
        return end

    try:
        end = skip(parse(0, '', 0))
        if end != len(source):
            raise JsonLocationError('El documento contiene texto después del valor JSON.', end)
    except (JsonLocationError, json.JSONDecodeError) as error:
        pos = error.at if isinstance(error, JsonLocationError) else error.pos
        line = bisect_right(starts, pos)
        return result('json', 'invalid', 'JSON inválido. ' + str(error).split(': line ')[0],
                      line=line, column=pos - starts[line-1] + 1, text=source[:MAX_TEXT],
                      text_truncated=len(source) > MAX_TEXT)
    snippet_start = 0
    first_line = 1
    if hours:
        row = hours['line'] - 1
        begin = starts[max(0, row - 1)]
        end = starts[min(row + 2, len(starts)-1)] if row + 2 < len(starts) else len(source)
        position = starts[row] + hours['column'] - 1
        hours['context'] = source[max(begin, position - 110): min(end, position + 110)].strip()
        if position >= MAX_TEXT:
            first_line = max(1, row - 4)
            snippet_start = starts[first_line - 1]
            if position - snippet_start >= MAX_TEXT:
                first_line = row + 1
                snippet_start = max(starts[row], position - 120)
    return result('json', 'ok', 'Sintaxis JSON válida. Los campos se localizan en la captura.',
                  text=source[snippet_start:snippet_start + MAX_TEXT], text_start_line=first_line, total_lines=len(starts),
                  text_start_column=snippet_start - starts[first_line-1] + 1,
                  text_truncated=len(source) > MAX_TEXT, fields=fields,
                  fields_truncated=nodes > MAX_FIELDS and len(fields) == MAX_FIELDS, schema=schema,
                  schema_validated=False, hours=hours)


HOURS = re.compile(r'(?i)^\s*(?:primera respuesta|plazo de (?:la )?primera respuesta)'
                   r'\s*(?:en\s+|:\s*|de\s+)([1-9]\d{0,6})\s*(?:h(?:oras?)?)\.?\s*$')


def pdf_view(data, page_number, mode):
    import pypdfium2 as pdf
    from pypdfium2 import raw
    try:
        doc = pdf.PdfDocument(data)
    except pdf.PdfiumError as exc:
        if getattr(exc, 'err_code', None) == raw.FPDF_ERR_PASSWORD:
            return result('pdf', 'protected', 'El PDF requiere contraseña. Selecciona una copia autorizada.')
        raise
    with doc:
        pages = len(doc)
        if type(page_number) is not int or not 1 <= page_number <= pages:
            return result('pdf', 'out_of_range', 'Esa página no existe en la captura.', pages=pages)
        if raw.FPDF_GetSecurityHandlerRevision(doc) >= 0 and not raw.FPDF_GetDocUserPermissions(doc) & 16:
            return result('pdf', 'protected', 'El documento restringe la extracción. Selecciona una copia autorizada.', pages=pages)
        if mode == 'page_count':
            return result('pdf', 'ok', 'Páginas contadas en el índice del PDF.', pages=pages)
        candidates = []
        complete = True
        count_scanned = 0
        scan_pages = mode in ('inspect', 'text')
        nums = range(1, min(pages, MAX_PAGES) + 1) if scan_pages else [page_number]
        page_texts = []
        image_pages = []
        remaining_text = MAX_TEXT
        values = dict(page=page_number, pages=pages)
        for number in nums:
            with closing(doc[number - 1]) as page:
                width, height = page.get_size()
                if not all(math.isfinite(x) and 0 < x < 20_000 for x in (width, height)):
                    return result('pdf', 'limit', 'La geometría de la página excede el límite.', page=number, pages=pages)
                scale = min(1.65, 850 / width, 980 / height)
                pixel_w, pixel_h = math.ceil(scale * width), math.ceil(scale * height)
                posconv = pdf.PdfPosConv(page, (0, 0, pixel_w, pixel_h, 0))
                with closing(page.get_textpage()) as textpage:
                    chars = textpage.count_chars()
                    if chars > 30_000:
                        complete = False
                    text = (textpage.get_text_bounded() if chars <= 30_000 else textpage.get_text_range(0,30_000)) if chars else ''
                    if mode == 'text' and next(page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE]), None) is not None:
                        complete = False
                        image_pages.append(number)
                    if not text.strip():
                        count_scanned += 1
                    if mode == 'text':
                        excerpt = text[:remaining_text]
                        if len(excerpt) < len(text):
                            complete = False
                        if excerpt.strip():
                            page_texts.append(dict(page=number, text=excerpt))
                        remaining_text -= len(excerpt)
                    lines = text.splitlines()
                    search_from = 0
                    for index, line in enumerate(lines):
                        match = HOURS.fullmatch(line)
                        if not match or len(candidates) >= 8:
                            continue
                        quote = line.strip()
                        context = ' '.join(lines[max(0, index-1):index+2])[:350]
                        hit = dict(page=number, quote=quote, context=context, value=int(match[1]), unit='h')
                        with closing(textpage.search(quote, index=search_from, match_case=True)) as searcher:
                            where = searcher.get_next()
                            if where:
                                start, length = where
                                search_from = start + length
                                # PDF user coordinates retain native rotation/crop semantics.
                                rectangles = textpage.count_rects(start, length)
                                if rectangles:
                                    rect = list(textpage.get_rect(0))
                                    hit['pdf_rect'] = rect
                                    hit['char_start'] = start
                                    hit['char_count'] = length
                                    x1, y1 = posconv.to_bitmap(rect[0], rect[3])
                                    x2, y2 = posconv.to_bitmap(rect[2], rect[1])
                                    left, right = sorted((min(1, max(0, x / pixel_w)) for x in (x1, x2)))
                                    top, bottom = sorted((min(1, max(0, y / pixel_h)) for y in (y1, y2)))
                                    if right > left and bottom > top:
                                        hit['region'] = [left, top, right-left, bottom-top]
                        candidates.append(hit)
                    if mode == 'preview':
                        with closing(page.render(scale=scale, may_draw_forms=False, draw_annots=False)) as bitmap:
                            values['image'] = raster(bitmap.to_pil().copy())
                        values.update(text=text[:MAX_TEXT], text_truncated=chars > MAX_TEXT,
                                      width=width, height=height)
        complete = complete and (not scan_pages or pages <= MAX_PAGES) and count_scanned == 0
        if mode == 'text':
            first = page_texts[0] if page_texts else dict(page=page_number,text='')
            values.update(text=first['text'],page=first['page'],text_truncated=not complete,page_texts=page_texts,
                          pages_examined=len(nums), pages_with_text=len(page_texts), image_pages=image_pages)
        status = 'no_text' if count_scanned == len(nums) else 'ok'
        detail = ('No se detectó texto seleccionable. Puedes revisar la imagen de la página.'
                  if status == 'no_text' else 'Texto localizado en las páginas de la captura.')
        return result('pdf', status, detail, candidates=candidates, complete=complete,
                      scanned_pages=count_scanned, **values)


def member_kind(name):
    from .general_files import TEXT_SUFFIXES
    suffix = PurePosixPath(name).suffix.lower()
    return EXTENSIONS.get(suffix, 'text' if suffix in TEXT_SUFFIXES else 'other')


def path_key(name):
    return unicodedata.normalize('NFC', name).casefold()


def zip_view(data, page, member, mode):
    # Preflight the classic central directory before allocating one ZipInfo per entry.
    tail = data[-65557:]
    offset = tail.rfind(b'PK\x05\x06')
    if offset < 0 or len(tail) < offset + 22:
        return result('zip', 'invalid', 'Falta el directorio central del ZIP.')
    _, disk, central_disk, _, count, length, _, comment = struct.unpack_from('<4s4H2IH', tail, offset)
    if disk or central_disk or count > MAX_ENTRIES or length > 192 * 1024:
        return result('zip', 'limit', 'Se admiten paquetes de un volumen con hasta 160 entradas.')
    if offset + 22 + comment != len(tail):
        return result('zip', 'invalid', 'El cierre del ZIP no coincide con su longitud.')
    with zipfile.ZipFile(BytesIO(data)) as archive:
        infos = archive.infolist()
        if len(infos) != count or sum(i.file_size for i in infos) > 24 * MIB:
            return result('zip', 'limit', 'El paquete excede el inventario o tamaño total admitido.')
        seen = set()
        collisions = set()
        for info in infos:
            key = path_key(info.orig_filename.rstrip('/'))
            if key in seen:
                collisions.add(key)
            seen.add(key)
        entries = []
        chosen = None
        for info in infos:
            name = info.orig_filename
            parts = name.rstrip('/').split('/')
            kind = 'directory' if info.is_dir() else member_kind(name)
            why = ''
            if (len(name) > 240 or len(parts) > 8 or any(p in ('', '.', '..') for p in parts)
                    or any(c in name for c in '\\:') or any(ord(c) < 32 for c in name)):
                why = 'La ruta interna no admite una vista previa segura.'
            elif path_key(name.rstrip('/')) in collisions:
                why = 'El nombre se repite en el inventario.'
            elif info.flag_bits & 1:
                why = 'La entrada está cifrada.'
            elif stat.S_ISLNK(info.external_attr >> 16):
                why = 'El miembro es un enlace.'
            elif kind in ('other', 'directory', 'zip'):
                why = 'Inventario disponible. Este miembro carece de vista previa.'
            elif (info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                  or info.file_size > MAX_MEMBER or info.file_size > 200 * max(info.compress_size, 1)):
                why = 'La compresión o el tamaño exceden los límites de lectura.'
            entry = dict(path=name[:240], kind=kind, bytes=info.file_size, readable=not why, detail=why)
            entries.append(entry)
            if member and member == name:
                chosen = (info, entry)
        if not member:
            return result('zip', 'ok', 'Inventario local. Los miembros se leen dentro del paquete.', entries=entries)
        if not chosen:
            return result('zip', 'not_found', 'No se encontró esa entrada en esta captura.')
        info, entry = chosen
        if not entry['readable']:
            return result('zip', 'unsupported', entry['detail'], member=member)
        with archive.open(info) as stream:
            content = stream.read(MAX_MEMBER + 1)
        if len(content) != info.file_size or len(content) > MAX_MEMBER:
            return result('zip', 'invalid', 'El tamaño descomprimido difiere del inventario.')
        actual = classify(member, content)
        if actual == 'zip' or actual != entry['kind']:
            return result('zip', 'invalid', 'El tipo del miembro difiere de su entrada en el paquete.', member=member)
        inner = read(actual, content, page=page, mode=mode)
        inner.update(member=member, container_kind='zip', member_bytes=len(content))
        import hashlib
        inner['member_sha256'] = hashlib.sha256(content).hexdigest()
        return inner


def read(kind, data, *, page=1, member='', mode='preview'):
    try:
        if kind == 'pdf':
            return pdf_view(data, page, mode)
        if kind == 'json':
            return json_view(data)
        if kind == 'zip':
            return zip_view(data, page, member, mode)
        if kind in ('png', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'):
            return image_view(kind, data, mode)
        if kind == 'html':
            if len(data) > 262144:
                return result(kind, 'limit', 'El lector HTML admite hasta 256 KiB.')
            findings = audit_html(data)
            text = data.decode('utf-8-sig')
            return result(kind, 'ok', 'Se ejecutaron las cuatro comprobaciones HTML locales.',
                          text=text[:MAX_TEXT], text_truncated=len(text) > MAX_TEXT,
                          findings=findings[:100], findings_total=len(findings))
        from .general_files import general_view, xml_syntax
        view = general_view(kind, data)
        if mode == 'xml_syntax' and kind == 'text':
            view.update(xml_syntax(data))
        return view
    except ImportError:
        return result(kind, 'unavailable', 'El lector local requiere las dependencias de escritorio de esta versión.')
    except (ValueError, OSError, KeyError, EOFError, SyntaxError, OverflowError, RuntimeError, zipfile.BadZipFile, wave.Error) as exc:
        # Only actionable domain errors cross the IPC; native parser messages can include paths.
        if kind == 'pdf' and getattr(exc, 'err_code', None) == 4:
            return result(kind, 'protected', 'El PDF requiere contraseña. Selecciona una copia autorizada.')
        return result(kind, 'invalid', 'No se pudo leer la captura. Comprueba su formato o elige otra copia.')
