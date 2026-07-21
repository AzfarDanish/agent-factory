"""Minimal PDF generator that embeds PNG images without Pillow."""

import zlib
import struct
import os
from pathlib import Path


def _read_png(path):
    """Read PNG file and extract raw image data."""
    with open(path, 'rb') as f:
        data = f.read()
    
    # Verify PNG signature
    sig = data[:8]
    assert sig == b'\x89PNG\r\n\x1a\n', 'Not a valid PNG'
    
    pos = 8
    width = height = 0
    raw_data = b''
    color_type = 0
    bit_depth = 0
    
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos+4])[0]
        chunk_type = data[pos+4:pos+8]
        chunk_data = data[pos+8:pos+8+length]
        
        if chunk_type == b'IHDR':
            width = struct.unpack('>I', chunk_data[0:4])[0]
            height = struct.unpack('>I', chunk_data[4:8])[0]
            bit_depth = chunk_data[8]
            color_type = chunk_data[9]
        
        elif chunk_type == b'IDAT':
            raw_data += chunk_data
        
        elif chunk_type == b'IEND':
            break
        
        pos += 12 + length
    
    # Decompress
    raw = zlib.decompress(raw_data)
    
    # Convert RGB to the PDF's RGB bytes
    # Each row has a filter byte prefix
    return width, height, raw, color_type


def make_pdf(image_paths, output_path, title='Coloring Pages'):
    """Create a multi-page PDF from PNG images."""
    objects = []
    obj_num = [0]
    
    def new_obj():
        obj_num[0] += 1
        return obj_num[0]
    
    def obj_str(num, content):
        return f'{num} 0 obj\n{content}\nendobj'
    
    # Build pages
    pages = []
    page_objs = []
    stream_objs = []
    
    for idx, img_path in enumerate(image_paths):
        w, h, raw_bytes, color_type = _read_png(img_path)
        
        # Each row has a filter byte at the start (PNG format)
        # For grayscale: 1 byte per pixel + filter byte
        # For RGB: 3 bytes per pixel + filter byte
        bytes_per_pixel = 3 if color_type == 2 else 1
        row_size = w * bytes_per_pixel + 1  # +1 for filter byte
        
        # PDF uses filtered data (remove PNG filter byte, keep pixel data)
        filtered = b''
        for row_idx in range(h):
            start = row_idx * row_size + 1  # skip filter byte
            end = start + w * bytes_per_pixel
            filtered += raw_bytes[start:end]
        
        # Compress for PDF
        compressed = zlib.compress(filtered)
        
        width_pt = w * 0.75  # scale pixels to points
        height_pt = h * 0.75
        
        # Image XObject
        img_num = new_obj()
        img_stream = (
            f'<<\n'
            f'/Type /XObject\n'
            f'/Subtype /Image\n'
            f'/Width {w}\n'
            f'/Height {h}\n'
            f'/ColorSpace /DeviceRGB\n'
            f'/BitsPerComponent 8\n'
            f'/Length {len(compressed)}\n'
            f'/Filter /FlateDecode\n'
            f'>>\n'
            f'stream\n{compressed.decode("latin-1")}\nendstream'
        )
        stream_objs.append((img_num, img_stream))
        
        # Page content stream
        content_num = new_obj()
        
        # Scale image to fit A4 with margins
        margin = 28  # ~1cm in points
        max_w = 595 - 2 * margin  # A4 width in points
        max_h = 842 - 2 * margin  # A4 height in points
        scale = min(max_w / width_pt, max_h / height_pt)
        disp_w = width_pt * scale
        disp_h = height_pt * scale
        cx = (595 - disp_w) / 2
        cy = (842 - disp_h) / 2
        
        content = (
            f'q\n'
            f'{disp_w} 0 0 {disp_h} {cx} {cy} cm\n'
            f'/{img_num} Do\n'
            f'Q\n'
        )
        content_bytes = content.encode('latin-1')
        content_stream = (
            f'<< /Length {len(content_bytes)} >>\n'
            f'stream\n{content}\nendstream'
        )
        stream_objs.append((content_num, content_stream))
        
        # Page
        page_num = new_obj()
        page = (
            f'<<\n'
            f'/Type /Page\n'
            f'/Parent 1 0 R\n'
            f'/MediaBox [0 0 595 842]\n'
            f'/Contents {content_num} 0 R\n'
            f'/Resources << /XObject << /{img_num} {img_num} 0 R >> >>\n'
            f'>>'
        )
        page_objs.append((page_num, page))
        pages.append(page_num)
    
    # Pages tree (object 1)
    pages_str = ' '.join([f'{p} 0 R' for p in pages])
    pages_obj = f'<< /Type /Pages /Kids [{pages_str}] /Count {len(pages)} >>'
    
    # Catalog (object 2)
    catalog = f'<< /Type /Catalog /Pages 1 0 R >>'
    
    # Build PDF
    import io
    buf = io.BytesIO()
    buf.write(b'%PDF-1.4\n')
    
    # Write all objects
    all_objects = [(1, pages_obj)] + [(2, catalog)] + page_objs + stream_objs
    offsets = []
    
    for num, content in all_objects:
        offsets.append(buf.tell())
        if isinstance(content, str):
            buf.write(f'{num} 0 obj\n{content}\nendobj\n'.encode('latin-1'))
        else:
            buf.write(f'{num} 0 obj\n'.encode('latin-1'))
            buf.write(content.encode('latin-1'))
            buf.write(b'\nendobj\n')
    
    # Cross-reference table
    xref_offset = buf.tell()
    buf.write(b'xref\n')
    buf.write(f'0 {len(all_objects) + 1}\n'.encode())
    buf.write(b'0000000000 65535 f \n')
    for offset in offsets:
        buf.write(f'{offset:010d} 00000 n \n'.encode())
    
    # Trailer
    buf.write(b'trailer\n')
    buf.write(f'<< /Size {len(all_objects) + 1} /Root 2 0 R >>\n'.encode())
    buf.write(b'startxref\n')
    buf.write(f'{xref_offset}\n'.encode())
    buf.write(b'%%EOF')
    
    with open(output_path, 'wb') as f:
        f.write(buf.getvalue())
    
    return output_path


if __name__ == '__main__':
    import sys
    images = sys.argv[1:-1] if len(sys.argv) > 2 else [
        'output/cartoon/2026-07-21/bc4ecf50-7a1_78856ed3defd.png',
        'output/cartoon/2026-07-21/746cbaa2-07d_78856ed3defd.png',
    ]
    output = sys.argv[-1] if len(sys.argv) > 2 else 'Kids_Picnic_Coloring_Pages.pdf'
    result = make_pdf(images, output)
    print(f'PDF: {result} ({os.path.getsize(result)} bytes, {len(images)} pages)')
