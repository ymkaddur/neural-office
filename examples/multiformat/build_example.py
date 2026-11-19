"""Synthetic support-portal inputs for a local, repeatable review."""
from io import BytesIO
from pathlib import Path
import tempfile
import zipfile


def pdf_bytes(pages):
    """Build a small, valid PDF using standard fonts and explicit page positions."""
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    kids = []
    for lines in pages:
        number = len(objects) + 1
        kids.append(f'{number} 0 R')
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 470 540] '
                       f'/Resources << /Font << /F1 3 0 R >> >> /Contents {number+1} 0 R >>'.encode())
        stream = [b'BT /F1 16 Tf 44 495 Td']
        for line in lines:
            literal = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)').encode('latin1')
            stream.extend((b'(' + literal + b') Tj', b'0 -28 Td'))
        stream.append(b'ET')
        data = b'\n'.join(stream)
        objects.append(f'<< /Length {len(data)} >>\nstream\n'.encode() + data + b'\nendstream')
    objects[1] = f'<< /Type /Pages /Count {len(kids)} /Kids [{" ".join(kids)}] >>'.encode()
    output = BytesIO(b'')
    output.write(b'%PDF-1.4\n')
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(output.tell())
        output.write(f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n')
    start = output.tell()
    output.write(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for at in offsets[1:]:
        output.write(f'{at:010} 00000 n \n'.encode())
    output.write(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    return output.getvalue()


def _build_files(directory):
    from PIL import Image, ImageDraw
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    pdf = directory / 'especificacion.pdf'
    pdf.write_bytes(pdf_bytes([['Portal de soporte', 'Especificacion de entrega'],
                               ['Portal de soporte', 'Plazo de respuesta', 'Primera respuesta en 24 horas.']]))
    manifest = directory / 'manifiesto.json'
    manifest.write_text('{\n  "servicio": "soporte",\n  "idioma": "es",\n  "response_sla_hours": 48\n}\n', encoding='utf-8')
    images = []
    for name, size in [('portada.png', (960, 600)), ('movil.jpg', (360, 720))]:
        image = Image.new('RGB', size, '#f4f6f1')
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, size[0], 55), fill='#203a32')
        draw.text((20, 20), 'Portal de soporte', fill='white', font_size=18)
        draw.text((20, 94), 'Centro de ayuda', fill='#203a32', font_size=27)
        draw.text((20, 143), 'Encuentra ayuda para tu equipo.', fill='#203a32', font_size=17)
        for idx, label in enumerate(['Abrir una solicitud', 'Consultar mi estado', 'Acceso a la cuenta']):
            y = 208 + idx * 76
            draw.rounded_rectangle((20, y, size[0] - 20, y + 57), 6, fill='white', outline='#aebeb2')
            draw.text((32, y + 17), label, fill='#203a32', font_size=17)
        target = directory / name
        image.save(target)
        images.append(target)
    package = directory / 'entrega.zip'
    with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for file, member in [(pdf, 'documentacion/especificacion.pdf'), (manifest, 'manifiesto.json'),
                             (images[0], 'visual/portada.png'), (images[1], 'visual/movil.jpg')]:
            entry = zipfile.ZipInfo(member, date_time=(2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, file.read_bytes())
    return [pdf, package, manifest, *images]


def example_files(directory):
    """Write five deterministic example inputs, preserving any pre-existing user files."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        files = _build_files(temporary)
        targets = [directory / source.name for source in files]
        for source, target in zip(files, targets):
            if target.exists() and (target.is_symlink() or not target.is_file() or target.read_bytes() != source.read_bytes()):
                raise FileExistsError(f'Ya existe otro archivo en {target}. Elige una carpeta para el ejemplo.')
        for source, target in zip(files, targets):
            if not target.exists():
                with target.open('xb') as out:
                    out.write(source.read_bytes())
        return targets


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Crea un ejemplo local de revisión con cinco archivos reales.')
    parser.add_argument('directorio', type=Path, help='Carpeta de destino del ejemplo')
    for path in example_files(parser.parse_args().directorio):
        print(path)
