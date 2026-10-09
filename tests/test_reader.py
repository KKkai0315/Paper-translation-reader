"""Local behavioral tests. Standard library only; integration needs Poppler."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import sys
import copy
import hashlib
import math

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


prepare = module('prepare_pdf').prepare
build = module('build_reader').build
crop = module('crop_figures').crop
png_size = module('figure_assets').png_size


def write_demo_pdf(path):
    """Two original, synthetic pages; minimal PDF fixture, no external assets."""
    streams = [b'BT /F1 22 Tf 50 730 Td (Offline paper reader: demo) Tj 0 -40 Td /F1 12 Tf (This is an original synthetic test page.) Tj ET q 0.9 0.95 0.91 rg 60 420 210 120 re f 330 420 210 120 re f 0.1 0.35 0.25 RG 2 w 60 420 210 120 re S 330 420 210 120 re S 270 480 m 330 480 l S 320 485 m 330 480 l 320 475 l S Q BT /F1 18 Tf 112 480 Td (Input tokens) Tj 265 0 Td (KV cache) Tj ET',
               b'BT /F1 22 Tf 50 730 Td (Equations and tables) Tj 0 -40 Td /F1 12 Tf (f = 1 / [action time + inference latency]) Tj 0 -25 Td (Config A: 200 ms. Config B: 500 ms.) Tj ET']
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    objects += [f'<< /Length {len(s)} >>\nstream\n'.encode() + s + b'\nendstream' for s in streams]
    raw = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(raw))
        raw.extend(f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = len(raw)
    raw.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        raw.extend(f'{offset:010} 00000 n \n'.encode())
    raw.extend(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    path.write_bytes(raw)


def demo_translation(manifest):
    return {'schema_version': 1, 'source_sha256': manifest['source_sha256'],
            'title': '论文对照阅读 · 合成审计样例', 'subtitle': '两页自制测试文档；无真实论文内容',
            'coverage': '这是验证界面和脚本的合成样例，不是学术论文译稿。',
            'pages': [
                {'number': 1, 'label': '标题 / 说明', 'blocks': [
                    {'type': 'heading', 'level': 2, 'text': '离线论文对照阅读'},
                    {'type': 'paragraph', 'text': '这是自制的测试页面。左侧为原始 PDF 页面，右侧为中文内容。'},
                    {'type': 'note', 'text': '译注示例：补充说明与原文译文分开显示。'},
                    {'type': 'list', 'ordered': False, 'items': ['按页跳转与搜索', '调整字号；只看原文或译文']},
                    {'type': 'code', 'text': '# 以下文本应显示为代码，不能执行\nprint("<script>alert(1)</script>")'}]},
                {'number': 2, 'label': '公式 / 表格', 'blocks': [
                    {'type': 'heading', 'level': 2, 'text': '公式与表格'},
                    {'type': 'equation', 'text': 'f = 1 / (动作执行时长 + 推理延迟)'},
                    {'type': 'table', 'headers': ['配置', '延迟'], 'rows': [['A', '200 ms'], ['B', '500 ms']]},
                    {'type': 'caption', 'text': '表 1：测试配置延迟。'},
                    {'type': 'paragraph', 'text': '搜索“500 ms”可跳转并高亮这张表。'}]}]}


@unittest.skipUnless(all(shutil.which(c) for c in ('pdfinfo','pdftotext','pdftoppm')), 'Poppler is not installed')
class ReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='paper-reader-test-')
        cls.base = Path(cls.temp.name)
        cls.pdf = cls.base / 'input.pdf'
        write_demo_pdf(cls.pdf)
        cls.original = cls.pdf.read_bytes()
        cls.source = cls.base / 'source'
        cls.manifest = prepare(cls.pdf, cls.source, 72)
        cls.regions = {'schema_version': 1, 'source_sha256': cls.manifest['source_sha256'],
                       'figures': [{'id': 'demo', 'page': 1, 'bbox': [0.08, 0.30, 0.90, 0.49],
                                    'label': '图 1', 'caption': '图 1：输入 token 写入 KV 缓存。原图内文字不翻译。'}]}
        cls.regions_path = cls.base / 'regions.json'
        cls.regions_path.write_text(json.dumps(cls.regions))
        cls.figure = crop(cls.pdf, cls.source/'manifest.json', cls.regions_path, cls.source/'figures', 144)['blocks'][0]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def make_build(self, data, name='reader.html', manifest=None):
        with tempfile.TemporaryDirectory(dir=self.base) as tmp:
            output = Path(tmp) / name
            translation = Path(tmp) / 'translation.json'
            translation.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            build(manifest or self.source / 'manifest.json', translation, output)
            return output.read_text(encoding='utf-8')

    def test_prepare_has_real_pages_and_does_not_modify_pdf(self):
        self.assertEqual(self.manifest['page_count'], 2)
        self.assertIn('synthetic', (self.source/'text/page-0001.txt').read_text())
        self.assertTrue((self.source/'images/page-0002.png').read_bytes().startswith(b'\x89PNG'))
        self.assertEqual(self.original, self.pdf.read_bytes())

    def test_refuse_preparation_overwrite(self):
        with self.assertRaises(ValueError):
            prepare(self.pdf, self.source, 72)
        self.assertEqual(self.original, self.pdf.read_bytes())

    def test_embed_all_pages_and_escape_untrusted_text(self):
        data = demo_translation(self.manifest)
        data['title'] = '</title><script>alert(42)</script>@@SECTIONS@@'
        result = self.make_build(data)
        self.assertEqual(result.count('src="data:image/png;base64,'), 2)
        self.assertEqual(result.count('<script '), 1)
        self.assertIn('&lt;script&gt;alert(42)&lt;/script&gt;@@SECTIONS@@', result)
        self.assertIn('connect-src \'none\'', result)
        self.assertNotIn('<script>alert(', result)

    def test_missing_duplicate_or_reordered_pages_rejected(self):
        for indices in ([0], [0,0], [1,0]):
            data = demo_translation(self.manifest)
            data['pages'] = [data['pages'][i] for i in indices]
            with self.assertRaises(ValueError):
                self.make_build(data)

    def test_untranslated_template_rejected(self):
        data = json.loads((self.source/'translation.template.json').read_text())
        with self.assertRaises(ValueError):
            self.make_build(data)

    def test_fingerprint_mismatch_rejected(self):
        data = demo_translation(self.manifest)
        data['source_sha256'] = '0'*64
        with self.assertRaises(ValueError):
            self.make_build(data)

    def test_malformed_table_rejected(self):
        data = demo_translation(self.manifest)
        data['pages'][1]['blocks'][2]['rows'][0].append('extra cell')
        with self.assertRaises(ValueError):
            self.make_build(data)

    def test_image_traversal_and_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory(dir=self.base) as tmp:
            folder = Path(tmp)
            outside = self.source/'images/page-0001.png'
            (folder/'linked.png').symlink_to(outside)
            for image in ('../source/images/page-0001.png', str(outside), 'linked.png'):
                manifest = json.loads(json.dumps(self.manifest))
                manifest['pages'][0]['image'] = image
                path = folder/'manifest.json'
                path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    self.make_build(demo_translation(self.manifest), manifest=path)

    def test_refuse_html_overwrite(self):
        with tempfile.TemporaryDirectory(dir=self.base) as tmp:
            folder = Path(tmp)
            output = folder/'reader.html'
            output.write_text('existing user content')
            translated = folder/'translation.json'
            translated.write_text(json.dumps(demo_translation(self.manifest)))
            with self.assertRaises(ValueError):
                build(self.source/'manifest.json', translated, output)
            self.assertEqual(output.read_text(), 'existing user content')

    def figure_data(self):
        data = demo_translation(self.manifest)
        data['pages'][0]['blocks'].append(copy.deepcopy(self.figure))
        return data

    def test_real_crop_dimensions_and_source_unchanged(self):
        raw = (self.source/self.figure['image']).read_bytes()
        self.assertEqual(png_size(raw), (math.ceil(.90*1224)-math.floor(.08*1224),
                                        math.ceil(.49*1584)-math.floor(.30*1584)))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), self.figure['image_sha256'])
        self.assertEqual(self.original, self.pdf.read_bytes())

    def test_figure_embedding_caption_and_escaping(self):
        data = self.figure_data()
        data['pages'][0]['blocks'][-1]['caption'] = '<script>bad()</script> 图注'
        data['pages'][0]['blocks'][-1]['alt'] = '\" onerror=\"bad()'
        result = self.make_build(data)
        self.assertEqual(result.count('src="data:image/png;base64,'), 3)
        self.assertIn('<figcaption class="caption">&lt;script&gt;bad()&lt;/script&gt; 图注', result)
        self.assertNotIn(' onerror="bad()', result)

    def test_figure_wrong_page_source_and_asset_hash_rejected(self):
        for key, value in [('source_page', 2), ('source_page', True), ('source_sha256', '0'*64), ('image_sha256', '0'*64)]:
            data = self.figure_data()
            data['pages'][0]['blocks'][-1][key] = value
            with self.assertRaises(ValueError):
                self.make_build(data)

    def test_figure_paths_reject_absolute_traversal_and_symlink(self):
        outside = self.base/'outside.png'
        outside.write_bytes((self.source/self.figure['image']).read_bytes())
        link = self.source/'linked-figure.png'
        link.symlink_to(outside)
        try:
            for path in ('../outside.png', str(outside), 'linked-figure.png'):
                data = self.figure_data()
                data['pages'][0]['blocks'][-1]['image'] = path
                with self.assertRaises(ValueError):
                    self.make_build(data)
        finally:
            link.unlink()

    def test_crop_bad_regions_rejected_before_output(self):
        invalid = [('bbox', [0, 0, 1.1, 1]), ('bbox', [.5, .1, .2, .8]),
                   ('bbox', [0, 0, float('nan'), 1]), ('id', '../escape'), ('page', 3)]
        for key, value in invalid:
            regions = copy.deepcopy(self.regions)
            regions['figures'][0][key] = value
            path = self.base/'bad-regions.json'
            path.write_text(json.dumps(regions))
            out = self.source/'invalid-crop'
            with self.assertRaises(ValueError):
                crop(self.pdf, self.source/'manifest.json', path, out)
            self.assertFalse(out.exists())

    def test_crop_rejects_mixed_pdf_and_overwrite(self):
        with self.assertRaises(ValueError):
            crop(self.pdf, self.source/'manifest.json', self.regions_path, self.source/'figures')
        wrong = self.base/'wrong.pdf'
        wrong.write_bytes(self.original + b'\n% Different source\n')
        with self.assertRaises(ValueError):
            crop(wrong, self.source/'manifest.json', self.regions_path, self.source/'wrong-figures')
        with self.assertRaises(ValueError):
            crop(self.pdf, self.source/'manifest.json', self.regions_path, self.base/'outside-figures')


if __name__ == '__main__':
    unittest.main(verbosity=2)
