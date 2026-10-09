#!/usr/bin/env python3
"""Render specified PDF regions as original figure PNGs; never detect or translate labels."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import tempfile

from figure_assets import bbox, png_size, require
from prepare_pdf import run


def crop(pdf, manifest_path, regions_path, out, dpi=240):
    pdf, manifest_path = pdf.expanduser().resolve(), manifest_path.expanduser().resolve()
    root = manifest_path.parent
    out = out.expanduser().absolute()
    require(not out.exists() and not out.is_symlink(), f'Refusing to overwrite: {out}')
    require(out.parent.is_dir(), 'Create output parent first')
    require(out.resolve().is_relative_to(root) and out.resolve() != root, 'Figure output must be inside the source directory')
    require(type(dpi) is int and 72 <= dpi <= 600, 'DPI must be 72..600')
    require(shutil.which('pdftoppm'), 'pdftoppm is required; no dependencies are installed automatically')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    regions = json.loads(regions_path.read_text(encoding='utf-8'))
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    require(manifest.get('schema_version') == 1, 'Unsupported source manifest')
    require(manifest.get('source_sha256') == digest, 'Source PDF fingerprint mismatch')
    require(isinstance(regions, dict) and regions.get('schema_version') == 1, 'Unsupported regions schema')
    require(regions.get('source_sha256') == digest, 'Regions belong to a different source PDF')
    entries = regions.get('figures')
    count = manifest.get('page_count')
    require(type(count) is int and count > 0, 'Invalid source page count')
    require(isinstance(entries, list) and entries, 'No figure regions supplied')
    seen = set()
    for entry in entries:
        require(isinstance(entry, dict), 'Each region must be an object')
        figure_id = entry.get('id')
        require(isinstance(figure_id, str) and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', figure_id), 'Invalid figure id')
        require(figure_id not in seen, 'Duplicate figure id')
        seen.add(figure_id)
        require(type(entry.get('page')) is int and 1 <= entry['page'] <= count, 'Invalid source page')
        bbox(entry.get('bbox'))
        for name in ('label', 'caption'):
            require(isinstance(entry.get(name), str) and entry[name].strip(), f'{name} is required')
        require(isinstance(entry.get('alt', ''), str), 'alt must be text')
    blocks = []
    # Render each selected page at the final DPI to measure actual pixel dimensions,
    # including rotation. Re-render crop rectangles with the exact same Poppler options.
    with tempfile.TemporaryDirectory(prefix='.figure-crop-', dir=out.parent) as temp:
        temp = Path(temp)
        stage = temp / 'figures'
        stage.mkdir()
        sizes = {}
        for entry in entries:
            page = entry['page']
            if page not in sizes:
                full = temp / f'page-{page}'
                run(['pdftoppm', '-f', str(page), '-l', str(page), '-singlefile', '-r', str(dpi), '-png', str(pdf), str(full)])
                sizes[page] = png_size(full.with_suffix('.png').read_bytes())
            width, height = sizes[page]
            left, top, right, bottom = entry['bbox']
            x, y = math.floor(left * width), math.floor(top * height)
            w, h = math.ceil(right * width) - x, math.ceil(bottom * height) - y
            prefix = stage / entry['id']
            run(['pdftoppm', '-f', str(page), '-l', str(page), '-singlefile', '-r', str(dpi), '-x', str(x), '-y', str(y), '-W', str(w), '-H', str(h), '-png', str(pdf), str(prefix)])
            raw = prefix.with_suffix('.png').read_bytes()
            require(png_size(raw) == (w, h), 'Unexpected crop size; inspect PDF page geometry')
            blocks.append({'type': 'figure', 'image': (out.resolve().relative_to(root) / (entry['id'] + '.png')).as_posix(),
                           'source_page': page, 'source_sha256': digest, 'bbox': entry['bbox'],
                           'dpi': dpi, 'image_sha256': hashlib.sha256(raw).hexdigest(),
                           'label': entry['label'], 'alt': entry.get('alt') or entry['label'], 'caption': entry['caption']})
        payload = {'schema_version': 1, 'source_sha256': digest, 'blocks': blocks}
        (stage / 'figure-blocks.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        out.mkdir()  # Exclusive: never replace an existing output directory.
        for child in stage.iterdir():
            shutil.move(str(child), str(out / child.name))
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--regions', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--dpi', type=int, default=240)
    args = parser.parse_args()
    try:
        result = crop(args.pdf, args.manifest, args.regions, args.out, args.dpi)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Error: {exc}\n')
    print(f"Cropped {len(result['blocks'])} figures: {args.out.absolute()}")


if __name__ == '__main__':
    main()
