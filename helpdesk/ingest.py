"""Build the vector store from every document in sources/.

Supported formats: PDF (text or scanned), DOCX, TXT/MD, HTML, CSV.
Scanned PDF pages are OCR'd locally with RapidOCR. If a file named
``<document>.ocr.txt`` sits next to a PDF, it is used instead of OCR
(pages separated by lines of the form ``=== PAGE n ===``).

Sub-folders of sources/ are read too. Paths matching a pattern in
``sources/.ingestignore`` (one glob per line) are skipped. Titles and dates come
from ``sources/catalog.csv`` (keyed by path relative to sources/) and, as a
fallback, from a dataset ``sources/index.csv`` (file,title,category,source,date).

Usage:  python -m helpdesk.ingest      (always rebuilds the collection from scratch)
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path

import chromadb
import ollama

from . import config

MIN_PAGE_CHARS = 40  # a PDF page with less extractable text than this is treated as scanned
OCR_SCALES = (1.5, 2.0, 3.0)
CATALOG_FILE = "catalog.csv"
INDEX_FILE = "index.csv"
IGNORE_FILE = ".ingestignore"
SKIP_SUFFIXES = (".ocr.txt",)
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                      "nov", "dec"], 1)}


# ---------------------------------------------------------------- loading

def clean(text: str) -> str:
    text = text.replace("​", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def latest_date(text: str) -> str:
    """'21 Sep 2026 (reminder 23 Sep 2026)' -> '2026-09-23'. ISO dates are kept as they are."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text.strip()):
        return text.strip()
    found = [(int(y), MONTHS[m[:3].lower()], int(d))
             for d, m, y in re.findall(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", text) if m[:3].lower() in MONTHS]
    return "%04d-%02d-%02d" % max(found) if found else ""


def load_catalog(sources: Path) -> dict[str, dict]:
    """Document titles and dates keyed by path relative to sources/.
    sources/catalog.csv (filename,title,doc_type,date) wins over sources/index.csv."""
    catalog = {}
    index = sources / INDEX_FILE
    if index.exists():
        with index.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                # "[IMPORTANT]: Fee Payment ..." -> "Fee Payment ...": brackets would break "[Source: ...]" citations
                title = re.sub(r"^\[[^\]]*\]:?\s*", "", row.get("title", "")).replace("[", "(").replace("]", ")")
                catalog[row["file"].strip()] = {"title": title, "doc_type": row.get("category", ""),
                                                "date": latest_date(row.get("date", ""))}
    path = sources / CATALOG_FILE
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                catalog[row["filename"].strip()] = {**row, "date": latest_date(row.get("date", ""))}
    return catalog


def load_ignore(sources: Path) -> list[str]:
    path = sources / IGNORE_FILE
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


def source_files(sources: Path) -> list[tuple[str, Path]]:
    """(path relative to sources/, path) of every document to index."""
    from fnmatch import fnmatch

    ignore = load_ignore(sources) + [CATALOG_FILE, INDEX_FILE, IGNORE_FILE]
    files = []
    for path in sorted(sources.rglob("*")):
        rel = path.relative_to(sources).as_posix()
        if (not path.is_file() or path.name.startswith(".") or path.name.endswith(SKIP_SUFFIXES)
                or any(fnmatch(rel, pattern) for pattern in ignore)):
            continue
        files.append((rel, path))
    return files


def title_from_filename(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"^[\d.]+_", "", stem)
    return re.sub(r"[_\-]+", " ", stem).strip()


_ocr_engine = None


def respace_ocr(text: str) -> str:
    """RapidOCR often drops the spaces between English words ("attendancefallsbelow").
    Split unknown letter runs into dictionary words and restore spaces after punctuation."""
    try:
        import wordninja
    except ImportError:
        return text
    model = wordninja.DEFAULT_LANGUAGE_MODEL
    known = model._wordcost

    def split_run(m: re.Match) -> str:
        word = m.group(0)
        if word.lower() in known or word.isupper():
            return word
        parts = model.split(word)
        return " ".join(parts) if all(len(p) > 1 or p.lower() in "ai" for p in parts) else word

    text = re.sub(r"[A-Za-z]{5,}", split_run, text)
    return re.sub(r"([a-z%][.,;:])([A-Za-z])", r"\1 \2", text)


def ocr_page(pdf_path: Path, page_index: int) -> str:
    global _ocr_engine
    try:
        import pypdfium2
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        print(f"  ! OCR libraries missing, cannot read scanned page {page_index + 1} of {pdf_path.name}")
        return ""
    import numpy as np

    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    doc = pypdfium2.PdfDocument(str(pdf_path))
    # The text detector occasionally skips a whole line at one resolution (it dropped a bullet of
    # the attendance circular at 2x), so OCR at several scales and keep the most complete reading.
    readings = []
    for scale in OCR_SCALES:
        image = doc[page_index].render(scale=scale).to_pil().convert("RGB")
        result, _ = _ocr_engine(np.array(image))
        readings.append(" ".join(line[1] for line in (result or [])))
    return respace_ocr(max(readings, key=lambda t: len(t.replace(" ", ""))))


def read_sidecar(path: Path) -> list[str] | None:
    sidecar = path.with_name(path.name + ".ocr.txt")
    if not sidecar.exists():
        return None
    parts = re.split(r"^=== PAGE \d+ ===\s*$", sidecar.read_text(encoding="utf-8"), flags=re.M)
    return [p for p in parts if p.strip()]


SERIAL_HEADERS = {"s.n", "s.n.", "s.no", "s.no.", "sr.no.", "sl.no.", "no."}
DATE_RE = re.compile(r"\d{1,2}(st|nd|rd|th)?[ -]*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", re.I)


def is_layout_grid(rows: list[list]) -> bool:
    """Layout grids with merged cells (e.g. academic calendars) have a mostly empty first row."""
    return sum(not (h or "").strip() for h in rows[0]) * 3 > len(rows[0])


def column_edges(table) -> set[int]:
    return {round(c[0] / 5) for c in table.cells} | {round(c[2] / 5) for c in table.cells}


def render_grid_table(page, table, carried: dict | None) -> tuple[list[str], dict | None]:
    """Render a calendar-style grid ("event | Semester I date | Semester II date | ...") from cell
    positions: in these PDFs every wrapped line is its own cell, so the rows of table.extract() do not
    line up. Each date cell is assigned to the column header above it and to the event label that
    shares the most height with it. ``carried`` ({"headers": [(x0, x1, label)], "edges": ...}) carries the
    column headers over to a continuation page whose table has the same column edges.
    Returns (sentences, headers to carry)."""
    cells = [(c, clean(page.within_bbox(c).extract_text())) for c in table.cells]
    cells = [(c, t) for c, t in cells if t]
    first_date_top = min((c[1] for c, t in cells if DATE_RE.search(t)), default=None)
    if first_date_top is None:
        return [], carried
    width = table.bbox[2] - table.bbox[0]
    head = [(c, t) for c, t in cells if c[3] <= first_date_top + 1 and not DATE_RE.search(t)
            and not re.fullmatch(r"[\W\d_]*|NA|N/A|((Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*[\s,-]*)+", t)]
    titles = [t for c, t in head if c[2] - c[0] >= 0.6 * width]
    columns = []
    for x0, x1, t in sorted(((c[0], c[2], t) for c, t in head if c[2] - c[0] < 0.6 * width), key=lambda h: h[:2]):
        if columns and min(x1, columns[-1][1]) - max(x0, columns[-1][0]) > 0.5 * (x1 - x0):  # stacked headers
            columns[-1] = (min(x0, columns[-1][0]), max(x1, columns[-1][1]), f"{columns[-1][2]} {t}")
        else:
            columns.append((x0, x1, t))
    if len(columns) >= 2:
        carried = {"headers": columns, "edges": {round(x / 5) for h in columns for x in h[:2]}}
    elif not carried or len(column_edges(table) & carried["edges"]) < 0.75 * len(carried["edges"]):
        return [], carried  # no header row, and the header columns of the previous grid do not line up
    headers = carried["headers"]
    body = [(c, t) for c, t in cells if (c, t) not in head]
    labels = sorted(((c, t) for c, t in body if (c[0] + c[2]) / 2 < headers[0][1]), key=lambda x: x[0][1])
    data = [(c, t) for c, t in body if (c[0] + c[2]) / 2 >= headers[0][1]]

    owned = {i: [] for i in range(len(labels))}
    for dc, dt in data:
        overlaps = [min(lc[3], dc[3]) - max(lc[1], dc[1]) for lc, _ in labels]
        if overlaps and max(overlaps) > 1:
            owned[overlaps.index(max(overlaps))].append((dc, dt))
    entries, pending = [], []  # entries: [label parts, data cells]
    for i, (lc, lt) in enumerate(labels):
        if owned[i]:
            entries.append([pending + [lt], owned[i]])
            pending = []
            continue
        # a wrapped line ("students", "verification of ...") continues the row above; a line that opens
        # a parenthesis or a new phrase ("First-Course Handout (including") starts the row below
        has_next = any(owned[j] for j in range(i + 1, len(labels)))
        balanced = lt.count("(") <= lt.count(")")
        continues = lt[:1].islower() or lt[:1] in ")," or (len(lt.split()) == 1 and balanced)
        if entries and balanced and (continues or not has_next):
            entries[-1][0].append(lt)
        else:
            pending.append(lt)

    def column(cell):
        xc = (cell[0] + cell[2]) / 2
        return min(headers[1:], key=lambda h: 0 if h[0] <= xc <= h[1] else min(abs(xc - h[0]), abs(xc - h[1])))[2]

    prefix = f"{' '.join(titles)} - " if titles else ""
    lines = []
    for parts, owned_cells in entries:
        by_column = {}
        for dc, dt in sorted(owned_cells, key=lambda x: (x[0][1], x[0][0])):
            by_column.setdefault(column(dc), []).append(dt)
        # "Column - value" rather than "Column: value": the chunker splits sentences at colons
        lines.append(prefix + " ".join(parts) + " | "
                     + " | ".join(f"{h} - {' '.join(v)}" for h, v in by_column.items()) + ".")
    return lines, carried


def page_text_with_tables(plumber_page, state: dict) -> str | None:
    """Flattened PDF tables lose the link between a row label and its column values
    ("Open (O) Electives (OE) 10 0 0"). For pages with ruled tables, return the text outside the
    tables with every table row written, right after the table's caption, as a sentence such as
    "Table 11.2 row - Course Type: Open (O) | Course Category: Electives (OE) | B.Tech. Regular: 10."
    Calendar-style grids are rendered by render_grid_table. ``state`` carries grid column headers
    from page to page. Returns None when the page has no table that could be rendered."""
    tables = [t for t in plumber_page.find_tables() if t.rows and len(t.rows) > 1 and len(t.rows[0].cells) > 1]
    rendered_tables = []  # (table, rows, grid sentences or None)
    for t in tables:
        rows = t.extract()
        if is_layout_grid(rows):
            lines, state["grid"] = render_grid_table(plumber_page, t, state.get("grid"))
            if lines:
                rendered_tables.append((t, rows, lines))
        elif any(DATE_RE.search(h or "") for h in rows[0]):
            continue  # the first row is data, not a header: leave the table in the plain page text
        else:
            rendered_tables.append((t, rows, None))
    if not rendered_tables:
        return None  # no table, or only grids that could not be rendered: use the plain page text
    outside = plumber_page
    for t, _, _ in rendered_tables:
        outside = outside.outside_bbox(t.bbox)
    body = clean(outside.extract_text() or "")
    captions = list(re.finditer(r"Table (\d+(?:\.\d+)?)\s+[A-Z][^.\d\u200b#]{3,90}", body))
    inserts = []  # (position in body, rendered rows)
    for i, (t, rows, grid_lines) in enumerate(rendered_tables):
        if grid_lines:
            inserts.append((len(body), " ".join(grid_lines)))
            continue
        label = f"Table {captions[i].group(1)}" if i < len(captions) else "Table"
        header = [clean(h or f"Column {j + 1}") for j, h in enumerate(rows[0])]
        previous = [""] * len(header)
        rendered = []
        for row in rows[1:]:
            # merged cells come back as None: carry the value down from the row above
            cells = [clean(c) if c is not None else previous[j] for j, c in enumerate(row[:len(header)])]
            previous = cells
            pairs = [f"{h}: {c}" for h, c in zip(header, cells)
                     if c and h.lower().replace(" ", "") not in SERIAL_HEADERS]
            if pairs:
                rendered.append(f"{label} row - " + " | ".join(pairs) + ".")
        inserts.append((captions[i].end() if i < len(captions) else len(body), " ".join(rendered)))
    for pos, rendered in sorted(inserts, key=lambda x: x[0], reverse=True):
        body = f"{body[:pos]}. {rendered} {body[pos:]}"
    return clean(body)


def load_pdf(path: Path) -> list[tuple[int, str]]:
    from pypdf import PdfReader

    sidecar = read_sidecar(path)
    if sidecar:
        return [(i + 1, clean(t)) for i, t in enumerate(sidecar)]
    try:
        import pdfplumber
        plumber = pdfplumber.open(str(path))
    except Exception:
        plumber = None
    pages, state = [], {}
    for i, page in enumerate(PdfReader(str(path)).pages):
        text = clean(page.extract_text() or "")
        if len(text) < MIN_PAGE_CHARS:
            text = clean(ocr_page(path, i))
            if text:
                print(f"  OCR used for page {i + 1}")
        elif plumber is not None:
            with_tables = page_text_with_tables(plumber.pages[i], state)
            if with_tables and len(with_tables) < 2.5 * len(text):  # else the table rendering ran away
                text = with_tables
        pages.append((i + 1, text))
    return pages


def load_docx(path: Path) -> list[tuple[int, str]]:
    import docx

    d = docx.Document(str(path))
    lines = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            lines.append(" | ".join(c.text for c in row.cells))
    return [(1, clean("\n".join(lines)))]


def load_html(path: Path) -> list[tuple[int, str]]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return [(1, clean(html.unescape(re.sub(r"<[^>]+>", " ", raw))))]


def load_csv(path: Path) -> list[tuple[int, str]]:
    with path.open(newline="", encoding="utf-8", errors="ignore") as f:
        rows = list(csv.DictReader(f))
    # a column with the same value in every row (e.g. provenance) only adds noise to each row
    constant = {k for k in (rows[0] if rows else {}) if len({r[k] for r in rows}) == 1 and len(rows) > 1}
    lines = ["; ".join(f"{k}: {v}" for k, v in row.items() if v and k not in constant) for row in rows]
    return [(1, clean(". ".join(lines)))]


LOADERS = {".pdf": load_pdf, ".docx": load_docx, ".txt": lambda p: [(1, clean(p.read_text(errors="ignore")))],
           ".md": lambda p: [(1, clean(p.read_text(errors="ignore")))], ".html": load_html, ".htm": load_html,
           ".csv": load_csv}


# ---------------------------------------------------------------- chunking

def chunk_text(text: str, size: int = config.CHUNK_SIZE, overlap: int = config.CHUNK_OVERLAP) -> list[str]:
    """Greedy sentence packing with a character-level overlap between consecutive chunks."""
    sentences = re.split(r"(?<=[.;:?!])\s+(?=[A-Z0-9(●•\[])", text)
    chunks, current = [], ""
    for sentence in sentences:
        while len(sentence) > size:  # very long table rows / run-on text
            head, sentence = sentence[:size], sentence[size - overlap:]
            if current:
                chunks.append(current)
                current = ""
            chunks.append(head)
        if len(current) + len(sentence) + 1 > size and current:
            chunks.append(current)
            current = current[-overlap:].split(" ", 1)[-1] + " " + sentence
        else:
            current = f"{current} {sentence}".strip()
    if current.strip():
        chunks.append(current)
    return chunks


def build_chunks(sources: Path) -> list[dict]:
    catalog = load_catalog(sources)
    records = []
    for rel, path in source_files(sources):
        loader = LOADERS.get(path.suffix.lower())
        if loader is None:
            print(f"- skipping unsupported file {rel}")
            continue
        meta = catalog.get(rel, {})
        title = meta.get("title") or title_from_filename(path.name)
        print(f"- {rel}  ->  '{title}' ({meta.get('date') or 'no date'})")
        n = 0
        for page, text in loader(path):
            for i, chunk in enumerate(chunk_text(text)):
                records.append({
                    "id": f"{rel}::p{page}::c{i}",
                    "text": chunk,
                    "source": rel,
                    "title": title,
                    "doc_type": meta.get("doc_type", ""),
                    "date": meta.get("date", ""),
                    "page": page,
                })
                n += 1
        print(f"    {n} chunks")
    return records


# ---------------------------------------------------------------- embedding

def embed(texts: list[str], kind: str) -> list[list[float]]:
    """nomic-embed-text expects task prefixes; other models ignore them harmlessly."""
    prefix = "search_document: " if kind == "document" else "search_query: "
    client = ollama.Client(host=config.OLLAMA_HOST)
    vectors = []
    for start in range(0, len(texts), 32):
        batch = [prefix + t for t in texts[start:start + 32]]
        vectors.extend(client.embed(model=config.EMBED_MODEL, input=batch)["embeddings"])
    return vectors


def embedding_text(rec: dict) -> str:
    return f"{rec['title']} (page {rec['page']}): {rec['text']}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args(argv)

    records = build_chunks(config.SOURCES_DIR)
    if not records:
        sys.exit(f"No documents found in {config.SOURCES_DIR}")

    config.VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
    try:
        client.delete_collection(config.COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(config.COLLECTION, metadata={"hnsw:space": "cosine"})

    print(f"Embedding {len(records)} chunks with {config.EMBED_MODEL} ...")
    vectors = embed([embedding_text(r) for r in records], kind="document")
    collection.add(
        ids=[r["id"] for r in records],
        embeddings=vectors,
        documents=[r["text"] for r in records],
        metadatas=[{k: r[k] for k in ("source", "title", "doc_type", "date", "page")} for r in records],
    )
    # Plain copy of the chunks for the BM25 keyword index.
    with (config.VECTOR_DIR / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Done. {collection.count()} chunks stored in {config.VECTOR_DIR}")


if __name__ == "__main__":
    main()
