
import hashlib
import json
import logging
import re
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT_DIR / "data" / "sample_resumes"
OUTPUT_DIR = ROOT_DIR / "data" / "extracted_resumes"
TEXT_DIR = OUTPUT_DIR
LOG_DIR = ROOT_DIR / "logs"

for folder in (INPUT_DIR, OUTPUT_DIR, LOG_DIR):
    folder.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "extraction.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)

HEADING_MAP = {
    "professional summary": "SUMMARY",
    "summary": "SUMMARY",
    "career objective": "SUMMARY",
    "objective": "SUMMARY",
    "work experience": "EXPERIENCE",
    "professional experience": "EXPERIENCE",
    "experience": "EXPERIENCE",
    "employment history": "EXPERIENCE",
    "education": "EDUCATION",
    "technical skills": "SKILLS",
    "skills": "SKILLS",
    "key skills": "SKILLS",
    "projects": "PROJECTS",
    "personal projects": "PROJECTS",
    "certifications": "CERTIFICATIONS",
    "achievements": "ACHIEVEMENTS",
    "languages": "LANGUAGES",
}

def read_pdf(path: Path) -> str:
    import pdfplumber
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=False)
            if text and text.strip():
                pages.append(text.strip())
    return "\n".join(pages)

def read_docx(path: Path) -> str:
    from docx import Document
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    doc = Document(path)
    parts = []
    for element in doc.element.body.iterchildren():
        if isinstance(element, CT_P):
            paragraph = Paragraph(element, doc)
            value = paragraph.text.strip()
            if value:
                parts.append(value)
        elif isinstance(element, CT_Tbl):
            table = Table(element, doc)
            for row in table.rows:
                cells = []
                for cell in row.cells:
                    cell_text = " ".join(p.text.strip() for p in cell.paragraphs if p.text.strip())
                    cells.append(cell_text)
                if any(cells):
                    parts.append(" | ".join(cells))
    return "\n".join(parts)

def ocr_fallback(path: Path) -> str:
    import pytesseract
    from PIL import Image
    import fitz

    if not shutil.which("tesseract"):
        windows_exe = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if windows_exe.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(windows_exe)
        else:
            raise RuntimeError("Tesseract OCR was not found. Install it or add it to PATH.")

    chunks = []
    if path.suffix.lower() == ".pdf":
        with fitz.open(path) as pdf:
            for page in pdf:
                if page.get_text().strip():
                    chunks.append(page.get_text().strip())
                else:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    text = pytesseract.image_to_string(image, lang="eng", config="--psm 3")
                    if text.strip():
                        chunks.append(text.strip())
    else:
        from io import BytesIO
        from zipfile import ZipFile
        from PIL import UnidentifiedImageError
        with ZipFile(path) as archive:
            image_names = sorted(
                n for n in archive.namelist()
                if n.startswith("word/media/") and not n.endswith("/")
            )
            for name in image_names:
                try:
                    with Image.open(BytesIO(archive.read(name))) as image:
                        text = pytesseract.image_to_string(
                            image.convert("RGB"), lang="eng", config="--psm 3"
                        )
                    if text.strip():
                        chunks.append(text.strip())
                except (UnidentifiedImageError, OSError):
                    logging.warning("Could not OCR embedded image %s in %s", name, path.name)
    return "\n".join(chunks)

def normalize_heading(line: str) -> str:
    """Return a canonical section label for a common resume heading."""
    value = re.sub(r"[\s:：|]+$", "", line.strip().lower())
    value = re.sub(r"\s+", " ", value).strip(" .#>*•-–—")
    # Match the same heading variants used by the extractor's cleaning pass.
    return HEADING_MAP.get(value, value.upper())


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\u2022", "-").replace("\uf0b7", "-")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    cleaned_lines = []
    previous_blank = False

    for original in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", original).strip()
        line = re.sub(r"\s+([,.;:])", r"\1", line)
        line = re.sub(r"([,;])(?=\S)", r"\1 ", line)

        if not line or re.fullmatch(r"[-_=*| ]{3,}", line):
            if cleaned_lines and not previous_blank:
                cleaned_lines.append("")
            previous_blank = True
            continue

        key = re.sub(r"[:\s]+$", "", line.lower())
        line = HEADING_MAP.get(key, line)
        cleaned_lines.append(line)
        previous_blank = False

    return "\n".join(cleaned_lines).strip()

def extract_basic_info(text: str) -> dict:
    email_match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.I)
    phone_match = re.search(
        r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3,5}\)?[\s.-]?)?\d{5,10}(?!\w)",
        text
    )
    first_lines = [line.strip() for line in text.splitlines() if line.strip()]
    name = None
    # Heuristic: use the first plausible short line that is not a contact/section heading.
    ignored = {"SUMMARY", "EXPERIENCE", "EDUCATION", "SKILLS", "PROJECTS", "CERTIFICATIONS"}
    for line in first_lines[:8]:
        if (len(line) <= 60 and "@" not in line and not re.search(r"\d", line)
                and line.upper() not in ignored and len(line.split()) <= 5):
            name = line
            break
    common_skills = [
        "Python", "Java", "JavaScript", "SQL", "Machine Learning", "NLP",
        "TensorFlow", "PyTorch", "Scikit-learn", "Pandas", "NumPy", "React",
        "Node.js", "Express", "FastAPI", "Flask", "AWS", "Azure", "Docker",
        "Git", "HTML", "CSS", "Power BI", "Excel", "Selenium", "Pytest",
        "PostgreSQL", "MySQL", "Spring Boot", "spaCy", "Hugging Face",
        "REST APIs", "Data Analysis", "Deep Learning"
    ]
    lower_text = text.lower()
    skills = [skill for skill in common_skills if skill.lower() in lower_text]
    return {
        "name": name,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0).strip() if phone_match else None,
        "skills": skills,
    }

def generate_candidate_id(
    email: str | None = None,
    phone: str | None = None,
    name: str | None = None,
    fallback: str | None = None,
) -> str:
    """Create a stable pseudonymous candidate ID from the best available identity field.

    Priority: normalized email, normalized phone, normalized name, then filename.
    Matching IDs across resumes depend on the chosen identity value being consistent.
    """
    normalized_phone = re.sub(r"\D", "", phone or "")

    if email and email.strip():
        identity = f"email:{email.strip().casefold()}"
    elif normalized_phone:
        identity = f"phone:{normalized_phone}"
    elif name and name.strip():
        normalized_name = re.sub(r"\s+", " ", name.strip().casefold())
        identity = f"name:{normalized_name}"
    else:
        fallback_name = Path(fallback).stem.casefold() if fallback else "unknown"
        identity = f"file:{fallback_name}"

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12].upper()
    return f"CAND-{digest}"


def extract_one(path: Path) -> dict:
    try:
        if path.suffix.lower() == ".pdf":
            raw = read_pdf(path)
        elif path.suffix.lower() == ".docx":
            raw = read_docx(path)
        else:
            raise ValueError("Only PDF and DOCX files are supported.")

        cleaned = clean_text(raw)
        if len(cleaned.strip()) < 20:
            logging.info("OCR fallback used for %s", path.name)
            cleaned = clean_text(ocr_fallback(path))

        if not cleaned:
            raise ValueError("No readable text found in the document.")

        info = extract_basic_info(cleaned)
        candidate_id = generate_candidate_id(
            email=info["email"],
            phone=info["phone"],
            name=info["name"],
            fallback=path.name,
        )
        return {
            "source_document": path.name,
            "candidate_id": candidate_id,
            "file_type": path.suffix.lower().lstrip("."),
            "status": "success",
            "name": info["name"],
            "email": info["email"],
            "phone": info["phone"],
            "skills": info["skills"],
        }
    except Exception as exc:
        logging.exception("FAILED | %s", path.name)
        return {
            "source_document": path.name,
            "candidate_id": generate_candidate_id(fallback=path.name),
            "file_type": path.suffix.lower().lstrip("."),
            "status": "failed",
            "error": str(exc),
            "name": None,
            "email": None,
            "phone": None,
            "skills": [],
        }

def extract_resume(path: str | Path) -> dict:
    """Extract text from a PDF/DOCX and return a stable testing/API payload.

    This wrapper preserves the legacy extractor contract while reusing the
    existing PDF, DOCX, cleaning, and OCR helpers.
    """
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(str(source))
    suffix = source.suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise ValueError("Only PDF and DOCX files are supported.")

    if suffix == ".pdf":
        raw = read_pdf(source)
    else:
        raw = read_docx(source)
    extracted = clean_text(raw or "")
    needs_ocr = len(extracted.strip()) < 20
    if suffix == ".docx":
        # Embedded scan images may coexist with a short placeholder paragraph.
        # OCR those images too instead of treating the placeholder as the resume.
        from zipfile import ZipFile
        try:
            with ZipFile(source) as archive:
                has_embedded_images = any(
                    name.startswith("word/media/") and not name.endswith("/")
                    for name in archive.namelist()
                )
        except Exception:
            has_embedded_images = False
        needs_ocr = needs_ocr or has_embedded_images
    if needs_ocr:
        ocr_text = clean_text(ocr_fallback(source))
        if ocr_text:
            extracted = "\n".join(part for part in (extracted, ocr_text) if part)
    if not extracted.strip():
        raise ValueError("No readable text found in the document.")

    file_type = suffix[1:]
    payload = {
        "source_document": source.name,
        "file_type": file_type,
        "extraction_status": "success",
        "extracted_text": extracted,
        "word_count": len(extracted.split()),
    }
    # Persist text and metadata to the configured output folder. Tests and
    # callers can override TEXT_DIR/OUTPUT_DIR without changing this function.
    output_dir = Path(TEXT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{source.stem}_{file_type}"
    (output_dir / f"{stem}.txt").write_text(extracted + "\n", encoding="utf-8")
    (Path(OUTPUT_DIR) / f"{stem}.json").parent.mkdir(parents=True, exist_ok=True)
    metadata_path = Path(OUTPUT_DIR) / f"{stem}.json"
    metadata_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def process_directory() -> None:
    files = sorted(
        p for p in INPUT_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".pdf", ".docx"}
    )
    results = [extract_one(path) for path in files]

    combined = {
        "total_resumes": len(results),
        "successful": sum(r["status"] == "success" for r in results),
        "failed": sum(r["status"] == "failed" for r in results),
        "resumes": results,
    }
    json_path = OUTPUT_DIR / "cleaned_resume_extraction.json"
    txt_path = OUTPUT_DIR / "cleaned_resume_extraction.txt"

    json_path.write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")

    text_sections = [
        f"TOTAL RESUMES: {combined['total_resumes']}",
        f"SUCCESSFUL: {combined['successful']}",
        f"FAILED: {combined['failed']}",
        ""
    ]
    for result in results:
        text_sections.append("=" * 72)
        text_sections.append(f"RESUME: {result['source_document']}")
        text_sections.append(f"CANDIDATE ID: {result['candidate_id']}")
        text_sections.append(f"STATUS: {result['status']}")
        if result["status"] == "success":
            text_sections.extend([
                f"NAME: {result['name'] or 'Not found'}",
                f"EMAIL: {result['email'] or 'Not found'}",
                f"PHONE: {result['phone'] or 'Not found'}",
                f"SKILLS: {', '.join(result['skills']) if result['skills'] else 'Not found'}",
            
            ])
        else:
            text_sections.append(f"ERROR: {result.get('error', 'Unknown error')}")
            text_sections.append("")
    txt_path.write_text("\n".join(text_sections).strip() + "\n", encoding="utf-8")

    print(f"Resumes found: {combined['total_resumes']}")
    print(f"Successful: {combined['successful']} | Failed: {combined['failed']}")
    print(f"JSON output: {json_path}")
    print(f"TXT output:  {txt_path}")

if __name__ == "__main__":
    process_directory()
