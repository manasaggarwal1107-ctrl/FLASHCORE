from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models.rossmann import DatasetImport, DatasetImportError

router = APIRouter(
    prefix="/api/imports",
    tags=["Dataset Imports"],
    dependencies=[Depends(require_roles("admin", "analyst"))],
)


class ImportRowErrorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row: int | None = None
    field: str | None = None
    message: str


class DataImportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str | None = None
    status: str | None = None
    dataset_source: str | None = None
    uploaded_by: str | None = None
    imported_rows: int | None = None
    rejected_rows: int | None = None
    duplicate_rows: int | None = None
    created_at: datetime | None = None
    provenance: str | None = None


class DataImportDetail(DataImportItem):
    errors: list[ImportRowErrorOut] | None = None


class DataImportListResponse(BaseModel):
    items: list[DataImportItem]
    total: int
    page: int
    page_size: int


def _map_import(imp: DatasetImport) -> dict:
    return {
        "id": str(imp.id),
        "filename": imp.source_file,
        "status": imp.status,
        "dataset_source": imp.source_name,
        "uploaded_by": "Rossmann Pipeline",
        "imported_rows": imp.successful_rows,
        "rejected_rows": imp.rejected_rows,
        "duplicate_rows": 0,
        "created_at": imp.imported_at,
        "provenance": (
            f"{imp.source_split} split"
            if imp.source_split
            else (f"URL: {imp.source_url}" if imp.source_url else None)
        ),
    }


@router.get("", response_model=DataImportListResponse)
def list_imports(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    search: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(DatasetImport)
    count_query = select(func.count(DatasetImport.id))

    if search:
        search_filter = (
            DatasetImport.source_file.ilike(f"%{search}%")
            | DatasetImport.source_name.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = db.scalar(count_query) or 0
    offset = (page - 1) * page_size
    query = query.order_by(DatasetImport.id.desc()).offset(offset).limit(page_size)
    records = db.scalars(query).all()

    items = [_map_import(imp) for imp in records]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{import_id}", response_model=DataImportDetail)
def get_import(
    import_id: int,
    db: Session = Depends(get_db),
):
    imp = db.get(DatasetImport, import_id)
    if imp is None:
        raise HTTPException(status_code=404, detail="Dataset import not found.")

    raw_errors = db.scalars(
        select(DatasetImportError)
        .where(DatasetImportError.import_id == import_id)
        .order_by(DatasetImportError.id.asc())
        .limit(100)
    ).all()

    errors = [
        {
            "row": err.source_row_number,
            "field": "record",
            "message": err.error_message,
        }
        for err in raw_errors
    ]

    detail = _map_import(imp)
    detail["errors"] = errors
    return detail
