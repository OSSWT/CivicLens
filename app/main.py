from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.config import PROJECT_ROOT, Settings, get_settings
from app.image_analysis import ImageAnalyzer, InvalidImageError
from app.models import (
    GeoJSONPoint,
    PhotoRecord,
    PublicConfig,
    ReportCategory,
    ReportResponse,
    ReportStatus,
    StatusUpdate,
)
from app.repository import (
    InMemoryReportRepository,
    MongoReportRepository,
    ReportRepository,
)
from app.storage import LocalPhotoStorage

STATIC_DIR = PROJECT_ROOT / "app" / "static"


def get_repository(request: Request) -> ReportRepository:
    return request.app.state.repository


def create_app(
    *,
    settings: Settings | None = None,
    repository: ReportRepository | None = None,
) -> FastAPI:
    active_settings = settings or get_settings()
    active_settings.upload_dir.mkdir(parents=True, exist_ok=True)
    storage = LocalPhotoStorage(active_settings.upload_dir)
    analyzer = ImageAnalyzer()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        mongo_client = None
        active_repository = repository
        if active_repository is None:
            if active_settings.use_in_memory:
                active_repository = InMemoryReportRepository()
            else:
                mongo_client, active_repository = MongoReportRepository.connect(
                    active_settings.mongo_uri,
                    active_settings.mongo_database,
                )
        await run_in_threadpool(active_repository.ensure_indexes)
        application.state.repository = active_repository
        try:
            yield
        finally:
            if mongo_client is not None:
                mongo_client.close()

    application = FastAPI(
        title="CivicLens API",
        version="0.1.0",
        description="Geospatial community reports with OpenCV photo-quality checks.",
        lifespan=lifespan,
    )
    application.state.settings = active_settings
    application.state.storage = storage
    application.state.analyzer = analyzer
    application.mount("/uploads", StaticFiles(directory=active_settings.upload_dir), name="uploads")
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    def require_admin(
        request: Request,
        x_admin_key: Annotated[str | None, Header()] = None,
    ) -> None:
        expected = request.app.state.settings.admin_api_key
        if not expected or not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
            raise HTTPException(status_code=401, detail="A valid X-Admin-Key header is required.")

    @application.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @application.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/config/public", response_model=PublicConfig, tags=["system"])
    def public_config() -> PublicConfig:
        return PublicConfig(
            google_maps_api_key=active_settings.google_maps_api_key,
            maps_enabled=bool(active_settings.google_maps_api_key),
        )

    @application.get("/api/reports", response_model=list[ReportResponse], tags=["reports"])
    def list_reports(
        report_repository: Annotated[ReportRepository, Depends(get_repository)],
        category: ReportCategory | None = None,
        status: ReportStatus | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> list[dict[str, Any]]:
        return report_repository.list_reports(
            category=category.value if category else None,
            status=status.value if status else None,
            limit=limit,
        )

    @application.get(
        "/api/reports/nearby",
        response_model=list[ReportResponse],
        tags=["reports"],
    )
    def nearby_reports(
        latitude: Annotated[float, Query(ge=-90, le=90)],
        longitude: Annotated[float, Query(ge=-180, le=180)],
        report_repository: Annotated[ReportRepository, Depends(get_repository)],
        radius_meters: Annotated[int, Query(ge=100, le=100_000)] = 5_000,
        category: ReportCategory | None = None,
        status: ReportStatus | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> list[dict[str, Any]]:
        return report_repository.nearby(
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            category=category.value if category else None,
            status=status.value if status else None,
            limit=limit,
        )

    @application.get(
        "/api/reports/{report_id}",
        response_model=ReportResponse,
        tags=["reports"],
    )
    def get_report(
        report_id: str,
        report_repository: Annotated[ReportRepository, Depends(get_repository)],
    ) -> dict[str, Any]:
        report = report_repository.get(report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found.")
        return report

    @application.post(
        "/api/reports",
        response_model=ReportResponse,
        status_code=201,
        tags=["reports"],
    )
    async def create_report(
        title: Annotated[str, Form(min_length=3, max_length=80)],
        category: Annotated[ReportCategory, Form()],
        description: Annotated[str, Form(max_length=500)],
        latitude: Annotated[float, Form(ge=-90, le=90)],
        longitude: Annotated[float, Form(ge=-180, le=180)],
        photo: Annotated[UploadFile, File()],
        report_repository: Annotated[ReportRepository, Depends(get_repository)],
    ) -> dict[str, Any]:
        content, content_type = await _read_upload(photo, active_settings.max_upload_bytes)
        try:
            analysis = await run_in_threadpool(analyzer.analyze, content)
            storage_name, photo_url = await run_in_threadpool(storage.save, content, content_type)
        except (InvalidImageError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        now = datetime.now(UTC)
        photo_record = PhotoRecord(
            url=photo_url,
            storage_name=storage_name,
            content_type=content_type,
            analysis=analysis,
            uploaded_at=now,
        ).model_dump(mode="python")
        document = {
            "title": title.strip(),
            "category": category.value,
            "description": description.strip(),
            "location": GeoJSONPoint(coordinates=(longitude, latitude)).model_dump(mode="python"),
            "status": ReportStatus.REPORTED.value,
            "before_photo": photo_record,
            "after_photo": None,
            "change_analysis": None,
            "created_at": now,
            "updated_at": now,
        }
        try:
            return await run_in_threadpool(report_repository.create, document)
        except Exception:
            await run_in_threadpool(storage.delete, storage_name)
            raise

    @application.patch(
        "/api/reports/{report_id}/status",
        response_model=ReportResponse,
        tags=["administration"],
        dependencies=[Depends(require_admin)],
    )
    def update_report_status(
        report_id: str,
        update: StatusUpdate,
        report_repository: Annotated[ReportRepository, Depends(get_repository)],
    ) -> dict[str, Any]:
        report = report_repository.update_status(report_id, update.status.value, datetime.now(UTC))
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found.")
        return report

    @application.post(
        "/api/reports/{report_id}/after-photo",
        response_model=ReportResponse,
        tags=["administration"],
        dependencies=[Depends(require_admin)],
    )
    async def add_after_photo(
        report_id: str,
        photo: Annotated[UploadFile, File()],
        report_repository: Annotated[ReportRepository, Depends(get_repository)],
    ) -> dict[str, Any]:
        existing = await run_in_threadpool(report_repository.get, report_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Report not found.")
        content, content_type = await _read_upload(photo, active_settings.max_upload_bytes)
        try:
            analysis = await run_in_threadpool(analyzer.analyze, content)
            before_content = await run_in_threadpool(
                storage.read,
                existing["before_photo"]["storage_name"],
            )
            change_analysis = await run_in_threadpool(analyzer.compare, before_content, content)
            storage_name, photo_url = await run_in_threadpool(storage.save, content, content_type)
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=409,
                detail="The original photo is unavailable.",
            ) from error
        except (InvalidImageError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        now = datetime.now(UTC)
        photo_record = PhotoRecord(
            url=photo_url,
            storage_name=storage_name,
            content_type=content_type,
            analysis=analysis,
            uploaded_at=now,
        ).model_dump(mode="python")
        updated = await run_in_threadpool(
            report_repository.set_after_photo,
            report_id,
            photo_record,
            change_analysis.model_dump(mode="python"),
            now,
        )
        if updated is None:
            await run_in_threadpool(storage.delete, storage_name)
            raise HTTPException(status_code=404, detail="Report not found.")
        old_after = existing.get("after_photo")
        if old_after:
            await run_in_threadpool(storage.delete, old_after.get("storage_name"))
        return updated

    @application.delete(
        "/api/reports/{report_id}",
        status_code=204,
        tags=["administration"],
        dependencies=[Depends(require_admin)],
    )
    def delete_report(
        report_id: str,
        report_repository: Annotated[ReportRepository, Depends(get_repository)],
    ) -> None:
        deleted = report_repository.delete(report_id)
        if deleted is None:
            raise HTTPException(status_code=404, detail="Report not found.")
        storage.delete(deleted.get("before_photo", {}).get("storage_name"))
        storage.delete((deleted.get("after_photo") or {}).get("storage_name"))

    return application


async def _read_upload(upload: UploadFile, max_upload_bytes: int) -> tuple[bytes, str]:
    content_type = (upload.content_type or "").lower()
    if content_type not in LocalPhotoStorage.EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Only JPEG, PNG, and WebP images are supported.",
        )
    content = await upload.read(max_upload_bytes + 1)
    await upload.close()
    if not content:
        raise HTTPException(status_code=422, detail="The uploaded image is empty.")
    if len(content) > max_upload_bytes:
        raise HTTPException(status_code=413, detail="The uploaded image is too large.")
    return content, content_type


app = create_app()
