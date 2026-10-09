#!/usr/bin/env python3
"""Extract a user-specified PDF locally into a NEW directory. No network calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def run(argv):
    result = subprocess.run(argv, check=True, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=600,
                            env={**os.environ, 'LC_ALL': 'C'})
    return result.stdout


def prepare(pdf, out, dpi):
    pdf, out = pdf.expanduser().resolve(), out.expanduser().absolute()
    if not pdf.is_file():
        raise ValueError(f'PDF not found: {pdf}')
    if out.exists() or out.is_symlink():
        raise ValueError(f'Refusing to overwrite existing output: {out}')
    if not out.parent.is_dir():
        raise ValueError(f'Create the output parent first: {out.parent}')
    if not 72 <= dpi <= 200:
        raise ValueError('DPI must be between 72 and 200.')
    commands = {}
    for name in ('pdfinfo', 'pdftotext', 'pdftoppm'):
        commands[name] = shutil.which(name)
        if not commands[name]:
            raise ValueError(f'Missing {name}; install Poppler separately. Nothing installed by this script.')
    info = run([commands['pdfinfo'], str(pdf)])
    match = re.search(r'^Pages:\s+(\d+)\s*$', info, re.M)
    if not match or int(match[1]) < 1:
        raise ValueError('Cannot determine PDF page count.')
    count = int(match[1])
    source_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    # All intermediates are confined to our fresh temporary directory.
    with tempfile.TemporaryDirectory(prefix='.paper-reader-', dir=out.parent) as tmp:
        work = Path(tmp)
        (work / 'images').mkdir()
        (work / 'text').mkdir()
        extracted = run([commands['pdftotext'], '-layout', str(pdf), '-'])
        texts = extracted.split('\f')
        if texts and not texts[-1].strip():
            texts.pop()
        if len(texts) != count:
            raise ValueError(f'Text/page boundary mismatch: {len(texts)} vs {count}. Inspect the PDF.')
        run([commands['pdftoppm'], '-r', str(dpi), '-png', str(pdf), str(work / 'images/render')])
        images = sorted((work / 'images').glob('render-*.png'),
                        key=lambda p: int(p.stem.split('-')[-1]))
        if len(images) != count:
            raise ValueError('Rendered image count does not match PDF page count.')
        entries, warnings = [], []
        for n, (image, page_text) in enumerate(zip(images, texts), 1):
            image_name, text_name = f'images/page-{n:04}.png', f'text/page-{n:04}.txt'
            image.rename(work / image_name)
            (work / text_name).write_text(page_text.strip() + '\n', encoding='utf-8')
            if len(page_text.strip()) < 40:
                warnings.append(f'Page {n}: little extracted text; inspect image (may be scan, figure, or blank page).')
            entries.append({'number': n, 'image': image_name, 'text': text_name})
        manifest = {'schema_version': 1, 'source_name': pdf.name,
                    'source_sha256': source_hash, 'page_count': count,
                    'dpi': dpi, 'warnings': warnings, 'pages': entries}
        title_match = re.search(r'^Title:\s+(.+)$', info, re.M)
        draft = {'schema_version': 1, 'source_sha256': source_hash,
                 'title': title_match[1].strip() if title_match else pdf.stem,
                 'subtitle': '', 'coverage': '',
                 'pages': [{'number': n, 'label': f'第 {n} 页', 'blocks': []}
                           for n in range(1, count + 1)]}
        for filename, data in [('manifest.json', manifest), ('translation.template.json', draft)]:
            (work / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        # mkdir is exclusive even if another process created the destination meanwhile.
        out.mkdir()
        for child in work.iterdir():
            shutil.move(str(child), str(out / child.name))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='New directory; parent must exist')
    parser.add_argument('--dpi', type=int, default=120)
    args = parser.parse_args()
    try:
        manifest = prepare(args.pdf, args.out, args.dpi)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Error: {exc}\n')
    print(f'Prepared {manifest["page_count"]} pages at {args.out.absolute()}')
    for warning in manifest['warnings']:
        print('Warning:', warning)


if __name__ == '__main__':
    main()
