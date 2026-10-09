# Translation data contract

`prepare_pdf.py` writes a manifest and an incomplete `translation.template.json`. Copy the latter outside the source folder and fill it. The builder rejects missing/duplicate/out-of-order pages, empty block lists, and a mismatched source fingerprint. It does not judge linguistic accuracy.

```json
{
  "schema_version": 1,
  "source_sha256": "copy the 64-character value from manifest.json",
  "title": "论文标题｜中文对照阅读",
  "subtitle": "作者，年份；所用版本",
  "coverage": "摘要、正文、图表、脚注和附录完整翻译；参考文献翻译标题，完整著录见原文。",
  "pages": [
    {
      "number": 1,
      "label": "摘要 / 引言",
      "blocks": [
        {"type": "heading", "level": 2, "text": "摘要"},
        {"type": "paragraph", "text": "这一页的完整译文……"},
        {"type": "equation", "text": "f ≤ 1 / (t_act + ℓ_S1 + ℓ_S2/H)　(4)"},
        {"type": "caption", "text": "图 1：图注译文。"},
        {"type": "note", "text": "译注：原文的两个数值不一致；此处分别保留。"},
        {"type": "code", "text": "# 中文注释\nresult = model(observation)"},
        {"type": "table", "headers": ["配置", "延迟"], "rows": [["A", "200 ms"], ["B", "500 ms"]]},
        {"type": "list", "ordered": false, "items": ["第一项", "第二项"]}
      ]
    }
  ]
}
```

- Include one entry for every physical PDF page, in order, starting at 1; printed page labels can be mentioned in `label`. A references-only page still needs translated reference titles or the explicitly agreed treatment.
- `heading.level` is 2–5; the document title uses H1. All fields containing prose are plain text. No HTML, Markdown, scripts, links, or LaTeX execution is accepted. `<script>` is displayed literally. Use readable Unicode/plain-text math; the source image retains the exact typesetting. If a complex formula cannot be faithfully linearized, describe symbols and point to the numbered original formula rather than fabricate an equivalent expression.
- `paragraph`, `caption`, `note`, `code`, and `equation` require `text`. Newlines in code/equations are preserved. A `list` requires nonempty `items` and boolean `ordered`. A table requires nonempty `headers` and `rows`; every row has exactly as many strings as the header.
- `figure` embeds an original crop with a Chinese caption. Generate its metadata using `scripts/crop_figures.py`; see [figures.md](figures.md). Required fields: `image` (relative PNG path), `source_page` (same physical page as the containing translation page), `source_sha256`, `image_sha256`, `bbox` (normalized coordinates), `dpi`, `label`, and `caption`; `alt` defaults to `label`. All prose is escaped. Existing translations without figure blocks remain supported.
- `coverage` is required and user-visible. State any omissions or unresolved passages here and on affected pages. Structural validity is not permission to claim completeness.
- The page labels populate the navigation menu. Search covers all translated blocks, including table cells and code. Search results go to and highlight the matching block.
- The manifest's page-image paths are resolved relative to its directory and must stay inside it. The builder accepts PNG images only. It embeds them as data URLs, so the HTML can be moved without its source directory.

# Input/output boundaries

Preparation reads one specified PDF and creates one fresh output directory containing `manifest.json`, `translation.template.json`, `text/page-NNNN.txt`, and `images/page-NNNN.png`. It uses Poppler executables without a shell. Cropping reads the specified PDF, matching manifest and region JSON; it creates a fresh figure directory inside the source tree containing PNGs and metadata. The build reads the specified manifest, translation JSON, page and figure PNGs inside the source tree, and the bundled HTML template, then creates one new HTML file. It does not read the source PDF during the build; the matching fingerprint prevents accidental mixing of the two JSON inputs, not malicious tampering. None of these scripts starts a server or accesses a remote service.
