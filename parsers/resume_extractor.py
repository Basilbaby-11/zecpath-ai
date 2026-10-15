
import json
import logging
import re
from pathlib import Path

import pdfplumber
from docx import Document


ROOT_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = ROOT_DIR / "data" / "sample_resumes"
TEXT_DIR = ROOT_DIR / "data" / "extracted_resumes"
OUTPUT_DIR = ROOT_DIR / "data" / "extracted_resumes"
LOG_DIR = ROOT_DIR / "logs"

for folder in (INPUT_DIR, TEXT_DIR, OUTPUT_DIR, LOG_DIR):
    folder.mkdir(parents=True, exist_ok=True)


logging.basicConfig(
    filename=LOG_DIR / "extraction.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)


HEADING_MAP = {
    "professional summary": "SUMMARY",
    "career objective": "SUMMARY",
    "work experience": "EXPERIENCE",
    "professional experience": "EXPERIENCE",
    "education": "EDUCATION",
    "technical skills": "SKILLS",
    "skills": "SKILLS",
    "projects": "PROJECTS",
    "certifications": "CERTIFICATIONS",
    "achievements": "ACHIEVEMENTS",
    "languages": "LANGUAGES",
}



def read_pdf(file_path: Path) -> str:
    """Extract PDF text in header, left-column, right-column order."""
    import pdfplumber

    all_pages = []

    def group_words_into_lines(words, tolerance=3):
        lines = []

        for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
            matching_line = next(
                (
                    line for line in lines
                    if abs(line[0]["top"] - word["top"]) <= tolerance
                ),
                None,
            )

            if matching_line is None:
                lines.append([word])
            else:
                matching_line.append(word)

        lines.sort(key=lambda line: min(w["top"] for w in line))

        return [
            " ".join(
                w["text"]
                for w in sorted(line, key=lambda w: w["x0"])
            )
            for line in lines
        ]

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()

            if not words:
                continue

            section_words = [
                w for w in words
                if w["text"].upper().rstrip(":")
                in {"PROFILE", "PROFESSIONAL"}
            ]

            if not section_words:
                text = page.extract_text()
                if text:
                    all_pages.append(text.strip())
                continue

            body_top = min(w["top"] for w in section_words)

            # This boundary fits the supplied two-column resume.
            # It is not a universal boundary for every PDF.
            column_boundary = page.width * 0.35

            header_words = [
                w for w in words
                if w["top"] < body_top - 3
            ]

            body_words = [
                w for w in words
                if w["top"] >= body_top - 3
            ]

            left_words = [
                w for w in body_words
                if w["x0"] < column_boundary
            ]

            right_words = [
                w for w in body_words
                if w["x0"] >= column_boundary
            ]

            parts = [
                "\n".join(group_words_into_lines(header_words)),
                "\n".join(group_words_into_lines(left_words)),
                "\n".join(group_words_into_lines(right_words)),
            ]

            all_pages.append(
                "\n\n".join(p for p in parts if p.strip())
            )

    return "\n\n".join(all_pages)


def read_docx(file_path: Path) -> str:
    """Extract DOCX paragraphs and preserve two-column table content."""
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl

    document = Document(file_path)
    parts = []

    def get_cell_lines(cell):
        """Return non-empty paragraphs from a table cell."""
        return [
            paragraph.text.strip()
            for paragraph in cell.paragraphs
            if paragraph.text.strip()
        ]

    # Preserve the order of paragraphs and tables in the document body.
    for element in document.element.body.iterchildren():
        if isinstance(element, CT_P):
            paragraph = Paragraph(element, document)
            text = paragraph.text.strip()

            if text:
                parts.append(text)

        elif isinstance(element, CT_Tbl):
            table = Table(element, document)

            # Heuristic: a single-row, two-cell table may represent
            # a two-column resume layout.
            if len(table.rows) == 1 and len(table.rows[0].cells) == 2:
                row = table.rows[0]

                # Extract the entire left column first.
                for line in get_cell_lines(row.cells[0]):
                    parts.append(line)

                # Then extract the entire right column.
                for line in get_cell_lines(row.cells[1]):
                    parts.append(line)

            else:
                # Preserve row structure for ordinary tables.
                for row in table.rows:
                    cells = [
                        " ".join(get_cell_lines(cell))
                        for cell in row.cells
                    ]

                    if any(cells):
                        parts.append(" | ".join(cells))

    return "\n".join(parts)



def _ocr_engine():
    """Configure Tesseract, including the common Windows install location."""
    import shutil
    import pytesseract

    windows_exe = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if shutil.which("tesseract"):
        pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract")
    elif windows_exe.is_file():
        pytesseract.pytesseract.tesseract_cmd = str(windows_exe)
    else:
        raise RuntimeError(
            "Tesseract OCR executable not found. Install Tesseract or add it to PATH."
        )
    return pytesseract


def ocr_pdf(file_path: Path) -> str:
    """Render image-only PDF pages and recognize text with Tesseract."""
    import fitz  # PyMuPDF; avoids the separate Poppler dependency
    from PIL import Image

    pytesseract = _ocr_engine()
    parts = []
    with fitz.open(file_path) as pdf:
        for page in pdf:
            # OCR only pages without a meaningful selectable text layer.
            if page.get_text().strip():
                parts.append(page.get_text().strip())
                continue
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            text = pytesseract.image_to_string(image, lang="eng", config="--psm 3")
            if text.strip():
                parts.append(text.strip())
    return "\n\n".join(parts)


def ocr_docx_images(file_path: Path) -> str:
    """Recognize text in images embedded in a DOCX package."""
    from io import BytesIO
    from zipfile import ZipFile
    from PIL import Image, UnidentifiedImageError

    pytesseract = _ocr_engine()
    parts = []
    with ZipFile(file_path) as archive:
        images = sorted(
            name for name in archive.namelist()
            if name.startswith("word/media/") and not name.endswith("/")
        )
        for name in images:
            try:
                with Image.open(BytesIO(archive.read(name))) as img:
                    text = pytesseract.image_to_string(
                        img.convert("RGB"), lang="eng", config="--psm 3"
                    )
                if text.strip():
                    parts.append(text.strip())
            except (UnidentifiedImageError, OSError):
                logging.warning("Skipping unsupported DOCX image: %s", name)
    return "\n\n".join(parts)


def normalize_heading(line: str) -> str:
    """Standardize recognized resume section headings."""
    key = re.sub(r"[:\s]+$", "", line.strip().lower())
    return HEADING_MAP.get(key, line.strip())


def clean_text(text: str) -> str:
    """Clean extracted text while preserving meaningful structure."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = text.replace("\u2022", "-")
    text = text.replace("\uf0b7", "-")

    cleaned_lines = []

    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()

        if not line:
            continue

        # Remove common decorative separators.
        if re.fullmatch(r"[-_=*•| ]{3,}", line):
            continue

        line = normalize_heading(line)
        cleaned_lines.append(line)

    # Avoid excessive blank lines without merging all sections.
    return "\n".join(cleaned_lines).strip()


def extract_resume(file_path: str | Path) -> dict:
    """Extract, clean and save a resume in structured formats."""
    file_path = Path(file_path)

    if not file_path.is_file():
        raise FileNotFoundError(f"Resume not found: {file_path}")

    extension = file_path.suffix.lower()

    if extension == ".pdf":
        raw_text = read_pdf(file_path)
    elif extension == ".docx":
        raw_text = read_docx(file_path)
    else:
        raise ValueError("Supported formats: PDF and DOCX")

    cleaned = clean_text(raw_text)

    if not cleaned:
        logging.info("OCR FALLBACK | %s", file_path.name)
        if extension == ".pdf":
            raw_text = ocr_pdf(file_path)
        else:
            raw_text = ocr_docx_images(file_path)
        cleaned = clean_text(raw_text)

    if not cleaned:
        raise ValueError(
            "No text extracted, including OCR fallback. "
            "Check image quality and Tesseract installation."
        )

    result = {
        "source_document": file_path.name,
        "file_type": extension[1:],
        "extraction_status": "success",
        "character_count": len(cleaned),
        "word_count": len(cleaned.split()),
        "extracted_text": cleaned,
    }

    output_stem = f"{file_path.stem}_{extension[1:]}"

    (TEXT_DIR / f"{output_stem}.txt").write_text(
        cleaned, encoding="utf-8"
    )

    (OUTPUT_DIR / f"{output_stem}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
)

    logging.info(
        "SUCCESS | %s | %s characters",
        file_path.name,
        len(cleaned),
    )

    return result


def process_directory() -> None:
    """Process every PDF and DOCX resume in the input folder."""
    files = sorted(
        path for path in INPUT_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".pdf", ".docx"}
    )

    for file_path in files:
        try:
            result = extract_resume(file_path)
            print(
                f"SUCCESS: {file_path.name} "
                f"({result['word_count']} words)"
            )
        except Exception:
            logging.exception("FAILED | %s", file_path.name)
            print(f"FAILED: {file_path.name} - see logs")


if __name__ == "__main__":
    process_directory()
