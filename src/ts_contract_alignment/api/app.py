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
from ..audit.database import DatabaseManager
from ..audit.models import (
    AlignmentModel,
    DocumentModel,
    GeneratedContractModel,
    ReviewSessionModel,
)
from ..interfaces.generator import GeneratedContract, Modification
from ..interfaces.review import ReviewAction, ReviewItem, ReviewSession
from ..parsers.serialization import DocumentSerializer
from ..review.final_exporter import FinalExporter
from ..review.review_manager import ReviewManager


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


# ---------------------------------------------------------------------------
# Review workflow API
# ---------------------------------------------------------------------------

_db_manager = DatabaseManager()
_review_manager = ReviewManager(db_manager=_db_manager)
_final_exporter = FinalExporter(output_dir="data/final")
_document_serializer = DocumentSerializer()


def _load_review_session(session_id: str) -> ReviewSession:
    """Helper to load a ReviewSession from the database via ReviewManager."""
    try:
        return _review_manager.get_session(session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _load_contract_and_template(session: ReviewSession) -> tuple[GeneratedContract, "ParsedDocument"]:
    """\
    Load GeneratedContract and its template ParsedDocument for a review session.

    This reconstructs domain objects from the persistence models so that
    FinalExporter can operate on them for finalized export.
    """
    from ..models.document import ParsedDocument  # local import to avoid cycles

    with _db_manager.get_session() as db:
        # Load generated contract model
        contract_model = (
            db.query(GeneratedContractModel)
            .filter(GeneratedContractModel.id == session.contract_id)
            .first()
        )
        if not contract_model:
            raise HTTPException(status_code=404, detail="Generated contract not found")

        # Reconstruct GeneratedContract dataclass
        mods: list[Modification] = []
        for m in contract_model.modifications or []:
            mods.append(
                Modification(
                    id=m.get("id"),
                    match_id=m.get("match_id"),
                    original_text=m.get("original_text", ""),
                    new_text=m.get("new_text", ""),
                    location_start=m.get("location_start", 0),
                    location_end=m.get("location_end", 0),
                    action=m.get("action"),  # type: ignore[arg-type]
                    source_ts_paragraph_id=m.get("source_ts_paragraph_id", ""),
                    confidence=m.get("confidence", 0.0),
                    annotations=m.get("annotations") or {},
                    status=m.get("status", "pending"),
                )
            )

        contract = GeneratedContract(
            id=str(contract_model.id),
            template_document_id="",  # filled below
            ts_document_id="",
            modifications=mods,
            revision_tracked_path=contract_model.revision_tracked_path or "",
            clean_version_path=contract_model.clean_version_path or "",
            generation_timestamp=contract_model.generation_timestamp.isoformat(),
        )

        # Load alignment to find template/TS document IDs
        alignment_model = (
            db.query(AlignmentModel)
            .filter(AlignmentModel.id == contract_model.alignment_id)
            .first()
        )
        if not alignment_model:
            raise HTTPException(status_code=404, detail="Alignment not found for contract")

        template_doc_id = alignment_model.template_document_id
        ts_doc_id = alignment_model.ts_document_id
        contract.template_document_id = str(template_doc_id)
        contract.ts_document_id = str(ts_doc_id)

        # Load and deserialize template ParsedDocument from DocumentModel
        template_model = (
            db.query(DocumentModel)
            .filter(DocumentModel.id == template_doc_id)
            .first()
        )
        if not template_model or not template_model.parsed_content:
            raise HTTPException(status_code=404, detail="Template document content not found")

        parsed: ParsedDocument = _document_serializer.deserialize(
            template_model.parsed_content
        )

    return contract, parsed


@app.get("/api/review/{session_id}")
async def get_review_session(session_id: str) -> JSONResponse:
    """Retrieve a review session with associated contract and document IDs.

    This endpoint exposes the review items (one per modification) together
    with basic metadata required by a frontend to render a review UI.
    """
    session = _load_review_session(session_id)

    # Also resolve basic document IDs via alignment/contract linkage
    with _db_manager.get_session() as db:
        contract_model = (
            db.query(GeneratedContractModel)
            .filter(GeneratedContractModel.id == session.contract_id)
            .first()
        )
        template_document_id = None
        ts_document_id = None
        if contract_model:
            alignment_model = (
                db.query(AlignmentModel)
                .filter(AlignmentModel.id == contract_model.alignment_id)
                .first()
            )
            if alignment_model:
                template_document_id = str(alignment_model.template_document_id)
                ts_document_id = str(alignment_model.ts_document_id)

    payload = {
        "id": session.id,
        "contract_id": session.contract_id,
        "ts_document_id": ts_document_id,
        "template_document_id": template_document_id,
        "completed_count": session.completed_count,
        "total_count": session.total_count,
        "session_timestamp": session.session_timestamp,
        "items": [
            {
                "modification_id": item.modification_id,
                "ts_term_id": item.ts_term_id,
                "clause_id": item.clause_id,
                "original_text": item.original_text,
                "new_text": item.new_text,
                "confidence": item.confidence,
                "action": item.action.value,
                "user_comment": item.user_comment,
            }
            for item in session.items
        ],
    }

    return JSONResponse(status_code=200, content=payload)


@app.post("/api/review/{session_id}/modifications/{mod_id}/accept")
async def accept_modification(session_id: str, mod_id: str) -> JSONResponse:
    """Mark a modification as accepted in the given review session."""
    try:
        item = _review_manager.update_item(
            session_id=session_id,
            item_id=mod_id,
            action=ReviewAction.ACCEPT,
            comment=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JSONResponse(
        status_code=200,
        content={
            "modification_id": item.modification_id,
            "action": item.action.value,
            "user_comment": item.user_comment,
        },
    )


@app.post("/api/review/{session_id}/modifications/{mod_id}/reject")
async def reject_modification(session_id: str, mod_id: str) -> JSONResponse:
    """Mark a modification as rejected in the given review session."""
    try:
        item = _review_manager.update_item(
            session_id=session_id,
            item_id=mod_id,
            action=ReviewAction.REJECT,
            comment=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JSONResponse(
        status_code=200,
        content={
            "modification_id": item.modification_id,
            "action": item.action.value,
            "user_comment": item.user_comment,
        },
    )


@app.post("/api/review/{session_id}/complete")
async def complete_review_session(session_id: str) -> JSONResponse:
    """Finalize a review session and export a finalized contract.

    The finalized document is generated by applying only the accepted (and
    modified) review items to the original template, using ``FinalExporter``.
    """
    # Load session
    session = _load_review_session(session_id)

    # Reconstruct contract and template document, then export
    contract, template_doc = _load_contract_and_template(session)
    output_path = _final_exporter.export_finalized_contract(
        template_doc=template_doc,
        contract=contract,
        session=session,
    )

    # Mark the session as completed in the database
    try:
        _review_manager.finalize_session(session_id)
    except ValueError as exc:
        # If the session was not found during finalize, still return the
        # generated path but signal the error to the caller.
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JSONResponse(
        status_code=200,
        content={
            "session_id": session_id,
            "final_document_path": output_path,
        },
    )

