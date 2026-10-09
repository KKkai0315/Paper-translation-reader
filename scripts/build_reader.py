#!/usr/bin/env python3
"""Build an offline page-aligned reader from local PNGs and translated JSON."""
import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import re
import secrets
from figure_assets import bbox, png_bytes


def require(ok, message):
    if not ok:
        raise ValueError(message)


def string(value, name, nonempty=True):
    require(isinstance(value, str), f'{name} must be a string')
    require(not nonempty or bool(value.strip()), f'{name} must not be empty')
    return value


def esc(value):
    return html.escape(value, quote=True)


def render_block(block, root=None, page_number=None, digest=None):
    require(isinstance(block, dict), 'Each block must be an object')
    kind = block.get('type')
    if kind == 'figure':
        require(root is not None, 'Figure needs a source directory')
        require(type(block.get('source_page')) is int and block['source_page'] == page_number,
                'Figure must be placed on its source page')
        require(block.get('source_sha256') == digest, 'Figure belongs to a different source PDF')
        bbox(block.get('bbox'))
        require(type(block.get('dpi')) is int and 72 <= block['dpi'] <= 600, 'Invalid figure DPI')
        raw = png_bytes(root, block.get('image'))
        require(hashlib.sha256(raw).hexdigest() == block.get('image_sha256'), 'Figure PNG fingerprint mismatch')
        encoded = base64.b64encode(raw).decode('ascii')
        label = esc(string(block.get('label'), 'figure.label'))
        alt = esc(string(block.get('alt', block.get('label')), 'figure.alt'))
        caption = esc(string(block.get('caption'), 'figure.caption'))
        return (f'<figure class="block figure"><button type="button" class="figure-open" '
                f'aria-label="放大{label}" data-label="{label}">'
                f'<img class="figure-image" loading="lazy" alt="{alt}" src="data:image/png;base64,{encoded}">'
                f'</button><figcaption class="caption">{caption}</figcaption>'
                f'<div class="figure-hint">原图 · 点击放大 · 图内文字保留原文</div></figure>')
    if kind in {'paragraph', 'caption', 'note', 'code', 'equation', 'heading'}:
        value = string(block.get('text'), 'block.text')
        text = esc(value)
        tags = {'paragraph': 'p', 'caption': 'p', 'note': 'aside',
                'code': 'pre', 'equation': 'pre'}
        if kind == 'heading':
            level = block.get('level', 2)
            require(type(level) is int and 2 <= level <= 5, 'heading.level must be 2–5')
            tag = f'h{level}'
        else:
            tag = tags[kind]
        return f'<{tag} class="block {kind}">{text}</{tag}>'
    if kind == 'list':
        items = block.get('items')
        require(isinstance(items, list) and items, 'list.items must be nonempty')
        require(type(block.get('ordered', False)) is bool, 'list.ordered must be boolean')
        tag = 'ol' if block.get('ordered', False) else 'ul'
        body = ''.join(f'<li>{esc(string(x, "list item"))}</li>' for x in items)
        return f'<{tag} class="block">{body}</{tag}>'
    if kind == 'table':
        headers, rows = block.get('headers'), block.get('rows')
        require(isinstance(headers, list) and headers, 'table.headers must be nonempty')
        require(isinstance(rows, list) and rows, 'table.rows must be nonempty')
        head = ''.join(f'<th scope="col">{esc(string(x, "table header", False))}</th>' for x in headers)
        body = []
        for row in rows:
            require(isinstance(row, list) and len(row) == len(headers), 'Table row width mismatch')
            body.append('<tr>' + ''.join(f'<td>{esc(string(x, "table cell", False))}</td>' for x in row) + '</tr>')
        return '<div class="block table-scroll"><table><thead><tr>' + head + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>'
    raise ValueError(f'Unsupported block type: {kind!r}')


def load(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(value, dict), f'{path.name} must contain an object')
    return value


def build(manifest_path, translation_path, out):
    manifest_path = manifest_path.expanduser().resolve()
    translation_path = translation_path.expanduser().resolve()
    out = out.expanduser().absolute()
    require(not out.exists() and not out.is_symlink(), f'Refusing to overwrite: {out}')
    require(out.parent.is_dir(), f'Create output parent first: {out.parent}')
    manifest, data = load(manifest_path), load(translation_path)
    require(manifest.get('schema_version') == 1 and data.get('schema_version') == 1, 'Unsupported schema version')
    digest = manifest.get('source_sha256')
    require(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest), 'Invalid source SHA-256')
    require(data.get('source_sha256') == digest, 'Translation belongs to a different source PDF')
    count = manifest.get('page_count')
    require(type(count) is int and count > 0, 'Invalid page count')
    for obj in [manifest, data]:
        pages = obj.get('pages')
        require(isinstance(pages, list) and len(pages) == count, 'Missing/extra pages')
        require(all(isinstance(p, dict) and type(p.get('number')) is int for p in pages), 'Invalid page entries')
        require([p['number'] for p in pages] == list(range(1, count + 1)), 'Pages must be consecutive, unique, and ordered')
    title = string(data.get('title'), 'title')
    subtitle = string(data.get('subtitle', ''), 'subtitle', False)
    coverage = string(data.get('coverage'), 'coverage')
    sections, options = [], []
    for source, page in zip(manifest['pages'], data['pages']):
        n = page['number']
        label = string(page.get('label'), 'page.label')
        blocks = page.get('blocks')
        require(isinstance(blocks, list) and blocks, f'Page {n} has no translation blocks')
        translated = '\n'.join(render_block(block, manifest_path.parent, n, digest) for block in blocks)
        raw = png_bytes(manifest_path.parent, source.get('image'))
        encoded = base64.b64encode(raw).decode('ascii')
        options.append(f'<option value="{n}">{n:02} · {esc(label)}</option>')
        sections.append(f'''<section class="spread" id="page-{n}" {'hidden' if n != 1 else ''}>
<div class="panel original"><div class="panel-label">原文 · 第 {n} / {count} 页 · 点击图像放大</div><div class="scan-scroll"><img class="scan" loading="lazy" alt="原文第 {n} 页" src="data:image/png;base64,{encoded}"></div></div>
<article class="panel translation"><div class="panel-label">译文 · 第 {n} / {count} 页</div><div class="reading">{translated}<div class="page-end">第 {n} / {count} 页</div></div></article></section>''')
    template_path = Path(__file__).resolve().parent.parent / 'assets/reader.html'
    template = template_path.read_text(encoding='utf-8')
    replacements = {'TITLE': esc(title), 'SUBTITLE': esc(subtitle), 'COVERAGE': esc(coverage),
                    'OPTIONS': '\n'.join(options), 'SECTIONS': '\n'.join(sections),
                    'NONCE': secrets.token_hex(16)}
    # Single-pass substitution: user content can contain placeholder-shaped text literally.
    result = re.sub(r'@@(TITLE|SUBTITLE|COVERAGE|OPTIONS|SECTIONS|NONCE)@@',
                    lambda m: replacements[m[1]], template)
    with out.open('x', encoding='utf-8') as handle:
        handle.write(result)
    return count, hashlib.sha256(result.encode('utf-8')).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--translation', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        count, digest = build(args.manifest, args.translation, args.out)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Error: {exc}\n')
    print(f'Built {count} pages: {args.out.absolute()}')
    print(f'Output SHA-256: {digest}')


if __name__ == '__main__':
    main()
