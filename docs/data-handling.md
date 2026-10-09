# Data handling and validation

## Model and scripts

The agent running this skill reads the paper and writes its translation. The Python scripts do not translate, invoke model APIs, or install dependencies. The host product's normal model and data-processing behavior still applies; an offline HTML output does not imply that translation happened entirely on-device.

| Component | Reads | Creates |
| --- | --- | --- |
| `prepare_pdf.py` | The specified PDF through Poppler | A fresh directory with page text, page PNGs, a manifest, and a translation template |
| `crop_figures.py` | The specified PDF, source manifest, and region JSON | A fresh figure directory inside the source tree, with PNGs and figure metadata |
| `build_reader.py` | The specified manifest, translation JSON, local PNGs, and bundled template | One new HTML file |

Source PDFs are not modified. Existing output paths are refused. Temporary render directories are cleaned up; a failure while publishing output can leave a partially populated new directory.

## Rendering and file boundaries

Poppler runs with argument arrays, without a shell. Scripts do not execute document code, fetch remote resources, read credentials, start listeners, or upload files. Image paths must be relative to and remain within the source directory after resolving symlinks.

The builder escapes prose rather than accepting raw HTML. Its reader uses a restrictive Content Security Policy and embeds PNGs as data URLs. It loads no external scripts, stylesheets, fonts, or telemetry. An agent may separately serve a deliverable over loopback for browser inspection; no script automatically starts a server.

## What checks establish

The builder checks page order and count, required blocks, table widths, source fingerprints, image paths, and figure metadata. The crop script checks the PDF fingerprint, page bounds, rectangle validity, and output dimensions. Figure PNG fingerprints help detect accidental asset changes.

These checks prevent common mix-ups; hashes are not tamper-proof authentication. They do not prove that every passage was translated accurately or that a crop contains the intended complete figure. Inspect source pages and every crop, especially legends, axes, multi-panel boundaries, and edge annotations.

## Public examples and scope

The bundled demo uses an original synthetic two-page PDF fixture. Real research papers, local work directories, and historical machine-specific audit logs are not included.

The test suite covers normal extraction/building and representative invalid inputs. It does not establish compatibility with all browsers, malformed or encrypted PDFs, very large documents, or OCR workflows. Translation quality requires a separate semantic review.
