"""Minimal FastAPI application for the TS Contract Alignment System.

This module exposes a simple HTTP API around the existing
ProcessingPipeline without changing its internal logic.

Usage (from project root, after installing fastapi and uvicorn):

    uvicorn ts_contract_alignment.api.app:app --reload

Then send a multipart/form-data POST request to /api/process with
`ts_file` and `template_file` fields.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from ..pipeline import PipelineConfig, ProcessingPipeline


app = FastAPI(title="TS Contract Alignment API", version="0.1.0")


def _get_use_embedding_from_env() -> bool:
    """Determine whether to enable embedding model based on environment.

    Uses TS_ALIGN_USE_EMBEDDING environment variable. Accepted truthy values:
    "1", "true", "yes", "y" (case-insensitive). If not set, defaults to True.
    """
    value = os.getenv("TS_ALIGN_USE_EMBEDDING")
    if value is None:
        return True
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _save_upload_to_temp(upload: UploadFile, temp_dir: Path) -> Path:
    """Save an uploaded file to a temporary directory and return its path."""
    suffix = Path(upload.filename or "").suffix or ""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir)
    try:
        content = upload.file.read()
        temp_file.write(content)
    finally:
        temp_file.close()
    return Path(temp_file.name)


@app.post("/api/process")
async def process_documents(
    ts_file: UploadFile = File(..., description="Term Sheet file (.docx/.pdf)"),
    template_file: UploadFile = File(..., description="Contract template file (.docx/.pdf)"),
) -> JSONResponse:
    """Run the TS-Contract alignment pipeline on uploaded documents.

    This endpoint:
    - Saves uploaded TS and template files to a temporary directory.
    - Runs ProcessingPipeline.process(ts_path, template_path).
    - Returns a JSON payload with high-level result information, including
      alignment statistics and any generated warnings/errors.
    """
    temp_dir = Path(tempfile.gettempdir()) / "ts_contract_alignment_api"
    temp_dir.mkdir(parents=True, exist_ok=True)

    ts_path: Optional[Path] = None
    template_path: Optional[Path] = None

    try:
        ts_path = _save_upload_to_temp(ts_file, temp_dir)
        template_path = _save_upload_to_temp(template_file, temp_dir)

        config = PipelineConfig(
            use_embedding_model=_get_use_embedding_from_env(),
        )
        pipeline = ProcessingPipeline(config=config)

        result = pipeline.process(str(ts_path), str(template_path))

        response_payload = {
            "success": result.success,
            "processing_time": result.processing_time,
            "errors": result.errors,
            "warnings": result.warnings,
        }

        if result.alignment is not None:
            response_payload["alignment"] = {
                "match_count": len(result.alignment.matches),
                "unmatched_terms_count": len(result.alignment.unmatched_terms),
                "unmatched_clauses_count": len(result.alignment.unmatched_clauses),
                "unmatched_terms": result.alignment.unmatched_terms,
                "unmatched_clauses": result.alignment.unmatched_clauses,
            }

        if result.contract is not None:
            response_payload["contract"] = {
                "id": result.contract.id,
                "template_document_id": result.contract.template_document_id,
                "ts_document_id": result.contract.ts_document_id,
                "modification_count": len(result.contract.modifications),
                # Expose generated file paths so clients can download them
                # or construct download links if needed.
                "revision_tracked_path": result.contract.revision_tracked_path,
                "clean_version_path": result.contract.clean_version_path,
            }

        return JSONResponse(status_code=200, content=response_payload)

    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    finally:
        # Do not delete temp files immediately; they may be useful for
        # debugging. In a production setting, consider scheduling cleanup.
        if "pipeline" in locals():
            try:
                pipeline.close()
            except Exception:  # noqa: BLE001
                pass


@app.get("/api/contracts/{contract_id}/download")
async def download_contract(
    contract_id: str,
    version: str = "clean",
) -> FileResponse:
    """Download a generated contract file by contract_id.

    This endpoint looks for files in the `data/generated` directory
    created by ContractGenerator. The generator uses a naming pattern
    like `contract_<id-prefix>_<timestamp>_tracked.docx` and
    `contract_<id-prefix>_<timestamp>_clean.docx`, where `<id-prefix>`
    is the first 8 characters of the contract ID.

    Args:
        contract_id: The contract ID returned from /api/process.
        version: "clean" for the final version or "tracked" for the
                 revision-tracked version.

    Returns:
        The requested .docx file as a streamed response.
    """
    if version not in {"clean", "tracked"}:
        raise HTTPException(status_code=400, detail="version must be 'clean' or 'tracked'")

    base_dir = Path("data/generated")
    if not base_dir.exists():
        raise HTTPException(status_code=404, detail="No generated contracts directory found")

    # ContractGenerator uses the first 8 characters of the UUID in the
    # filename; we follow the same convention to locate files.
    prefix = contract_id[:8]
    suffix = "clean" if version == "clean" else "tracked"
    pattern = f"contract_{prefix}_*_{suffix}.docx"

    matches = sorted(base_dir.glob(pattern))
    if not matches:
        raise HTTPException(status_code=404, detail="Generated contract file not found")

    # If multiple files match (e.g. multiple generations), return the
    # latest one by filename order (timestamp is embedded in name).
    target = matches[-1]

    return FileResponse(
        path=target,
        filename=target.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
