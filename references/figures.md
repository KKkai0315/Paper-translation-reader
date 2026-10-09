# Original figures in the Chinese panel

Include each paper figure on its physical source page in the Chinese panel by default. Keep all text inside the image unchanged; translate its caption below it. Tables may stay as searchable translated tables. Do not turn a figure into a generated illustration or extract only PDF embedded bitmaps: vector paths, axes, labels, and multiple panels can be separate PDF objects.

## Locate, crop, and inspect

1. Inspect the prepared `source/images/page-NNNN.png`. Locate the complete figure, including axes, legends, panel labels, arrows, and edge annotations. Exclude running headers, line numbers, body text, and the English caption. Leave a small margin. No automatic figure detection is implemented; the executing model supplies the rectangles.
2. Write `regions.json` outside the source folder. Use physical pages numbered from 1. `bbox` is `[left, top, right, bottom]`, normalized to 0..1 relative to the whole rendered page, with the origin at top left. For a page image W×H pixels, convert `[x0,y0,x1,y1]` to `[x0/W,y0/H,x1/W,y1/H]`. Copy the PDF fingerprint from `source/manifest.json`.

```json
{
  "schema_version": 1,
  "source_sha256": "copy the 64-character value from source/manifest.json",
  "figures": [
    {
      "id": "figure-01",
      "page": 3,
      "bbox": [0.09, 0.10, 0.49, 0.36],
      "label": "图 1",
      "alt": "图 1：流式推理结构图，图内文字保留原文",
      "caption": "图 1：完整中文图注。"
    }
  ]
}
```

3. Run the crop script. The output must be a fresh directory **inside** the manifest's source directory. Use 240 DPI by default, or 300 DPI for dense plots. It renders PDF content directly with Poppler, preserving original artwork, and writes PNGs plus `figure-blocks.json`.

```sh
python3 <skill-dir>/scripts/crop_figures.py --pdf /absolute/paper.pdf --manifest /absolute/task-output/source/manifest.json --regions /absolute/task-output/regions.json --out /absolute/task-output/source/figures --dpi 240
```

4. Inspect **every** output crop. Check the outside edges and each panel against the original page. If a legend, tick label, or annotation is clipped, adjust the rectangle and regenerate into a fresh directory. If a figure spans pages, use separate labeled crops on their respective pages. If a rectangle cannot separate the figure from other content, disclose that and choose a wider faithful crop rather than deleting original marks. Do not claim the script automatically verified visual completeness.
5. Copy each generated `figure` block into the corresponding page's `blocks`, at the figure's reading position. Its `caption` replaces the previous caption block; do not duplicate the caption. Preserve the generated `image`, `bbox`, `dpi`, `source_page`, `source_sha256`, and `image_sha256`. Do not manually invent hashes. Chinese `label`, `alt`, and `caption` may be edited. Do not translate or redraw labels inside the screenshot, or add a redundant label glossary unless requested.
6. Build normally. Images are embedded as PNG data URLs; the delivered HTML remains a single offline file. The right column scales figures to its width. Clicking or keyboard-activating a figure opens a modal with fit-to-window/original-pixel viewing, translated caption, and Escape/close-button dismissal. Captions participate in translation search; image pixels are not OCR-searchable.

## Provenance and limits

The crop script checks the PDF, preparation manifest, and region list share a source SHA-256. It measures the actual rendered page at the selected DPI before cropping, including rotated page geometry. The builder checks each figure's source fingerprint, page placement, PNG fingerprint, rectangle shape, DPI, and containment within the source directory. These checks prevent accidental asset mixing; they do not authenticate a maliciously edited manifest or prove the rectangle contains the correct figure.

The new script needs only Python standard library and existing `pdftoppm`; it calls no OCR/model/network services and installs nothing. Temporary page renders are removed after cropping. Figure PNGs enlarge the resulting HTML, particularly for dense heatmaps. Inspect figure clarity at both column width and full size before delivery.
