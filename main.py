import os
from fastapi import FastAPI, UploadFile, Header, HTTPException
from docling.document_converter import DocumentConverter

API_KEY = os.environ["SIREN_API_KEY"]  # set as a secret on the host

app = FastAPI()
converter = DocumentConverter()

@app.post("/extract")
async def extract(file: UploadFile, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    contents = await file.read()
    # Docling needs a path or file-like object; write to a temp file
    tmp_path = f"/tmp/{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(contents)

    result = converter.convert(tmp_path)
    os.remove(tmp_path)

    return {
        "markdown": result.document.export_to_markdown(),
        "structure": result.document.export_to_dict(),
    }