import os
import tempfile

from fastapi import FastAPI, UploadFile, Header, HTTPException
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat

API_KEY = os.environ.get("SIREN_API_KEY")
if not API_KEY:
    raise RuntimeError("SIREN_API_KEY environment variable is not set")

app = FastAPI()

# Siren's PDFs are digital text, not scans, so OCR and table-structure
# models aren't needed — skipping them avoids loading the heaviest models
# (EasyOCR in particular) and cuts memory use substantially.
pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = False
pipeline_options.do_table_structure = False

# Loaded once at startup so requests don't pay model-load cost repeatedly.
converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)


@app.get("/health")
async def health():
    """Lightweight endpoint for cold-start / connectivity checks from the app."""
    return {"status": "ok"}


@app.post("/extract")
async def extract(
    file: UploadFile,
    x_api_key: str = Header(None),
    debug: bool = False,
):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    contents = await file.read()

    # Docling's converter wants a path (or URL); write to a temp file.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        result = converter.convert(tmp_path)
        markdown = result.document.export_to_markdown()
        page_count = len(result.document.pages)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Extraction failed: {e}")
    finally:
        os.remove(tmp_path)

    response = {"markdown": markdown, "page_count": page_count}

    # Temporary diagnostic path — pass ?debug=true to also get Docling's raw
    # structured output (each text item's real `label`: section_header vs
    # text vs list_item, etc). Not used by the app in normal operation; only
    # for confirming whether the BERT sectioning bug originates in Docling's
    # own layout classification or in Siren's markdown-based parsing.
    # Remove this branch once diagnosed.
    if debug:
        response["structure"] = result.document.export_to_dict()

    return response

