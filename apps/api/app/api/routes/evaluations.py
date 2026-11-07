from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_csrf, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import PromptVersionListResponse
from app.schemas.eval import (
    AblationRequest,
    AblationResponse,
    EvalCompareResponse,
    EvalDatasetDetail,
    EvalDatasetListResponse,
    EvalDatasetOut,
    EvalResultListResponse,
    EvalResultOut,
    EvalReviewUpdate,
    EvalRunCreate,
    EvalRunDetail,
    EvalRunListResponse,
    EvalRunOut,
)
from app.services.admin_settings import list_prompt_versions
from app.services.evaluation import (
    compare_runs,
    create_imported_dataset,
    get_dataset_detail,
    get_run_detail,
    list_datasets,
    list_results,
    list_runs,
    review_result,
    run_ablation,
    run_evaluation,
)

router = APIRouter(prefix="/eval", tags=["evaluations"])


@router.get("/datasets", response_model=EvalDatasetListResponse)
async def datasets(
    user: User = Depends(require_permission("eval:manage")),
    db: AsyncSession = Depends(get_db),
) -> EvalDatasetListResponse:
    return EvalDatasetListResponse(items=await list_datasets(db, owner_id=user.id))


@router.get("/prompts", response_model=PromptVersionListResponse)
async def eval_prompts(
    user: User = Depends(require_permission("eval:manage")),
    db: AsyncSession = Depends(get_db),
) -> PromptVersionListResponse:
    return PromptVersionListResponse(
        items=await list_prompt_versions(db, owner_id=user.id)
    )


@router.post("/datasets/import", response_model=EvalDatasetOut, status_code=201)
async def import_dataset(
    file: UploadFile = File(...),
    name: str = Form(..., min_length=1, max_length=120),
    dataset_type: Literal["knowledge", "triage", "security"] = Form(...),
    version: str = Form("v1", max_length=30),
    user: User = Depends(require_permission("eval:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> EvalDatasetOut:
    content = await file.read()
    return await create_imported_dataset(
        db,
        name=name.strip(),
        dataset_type=dataset_type,
        version=version,
        filename=file.filename or "dataset.jsonl",
        content=content,
        user=user,
    )


@router.get("/datasets/{dataset_id}", response_model=EvalDatasetDetail)
async def dataset_detail(
    dataset_id: str,
    _: User = Depends(require_permission("eval:manage")),
    db: AsyncSession = Depends(get_db),
) -> EvalDatasetDetail:
    return await get_dataset_detail(db, dataset_id)


@router.post("/runs", response_model=EvalRunOut, status_code=201)
async def create_run(
    payload: EvalRunCreate,
    user: User = Depends(require_permission("eval:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> EvalRunOut:
    return await run_evaluation(db, payload=payload, user=user)


@router.post("/experiments", response_model=AblationResponse, status_code=201)
async def create_experiment(
    payload: AblationRequest,
    user: User = Depends(require_permission("eval:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> AblationResponse:
    return await run_ablation(db, payload=payload, user=user)


@router.get("/runs", response_model=EvalRunListResponse)
async def runs(
    dataset_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("eval:manage")),
    db: AsyncSession = Depends(get_db),
) -> EvalRunListResponse:
    return EvalRunListResponse(
        items=await list_runs(db, dataset_id=dataset_id, limit=limit)
    )


@router.get("/compare", response_model=EvalCompareResponse)
async def compare(
    baseline_run_id: str = Query(...),
    candidate_run_id: str = Query(...),
    _: User = Depends(require_permission("eval:manage")),
    db: AsyncSession = Depends(get_db),
) -> EvalCompareResponse:
    return await compare_runs(
        db,
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
    )


@router.get("/runs/{run_id}", response_model=EvalRunDetail)
async def run_detail(
    run_id: str,
    result_limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("eval:manage")),
    db: AsyncSession = Depends(get_db),
) -> EvalRunDetail:
    return EvalRunDetail(**await get_run_detail(db, run_id, result_limit=result_limit))


@router.get("/runs/{run_id}/results", response_model=EvalResultListResponse)
async def run_results(
    run_id: str,
    verdict: str = Query(default="all"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("eval:manage")),
    db: AsyncSession = Depends(get_db),
) -> EvalResultListResponse:
    return await list_results(
        db, run_id=run_id, verdict=verdict, offset=offset, limit=limit
    )


@router.patch(
    "/runs/{run_id}/results/{result_id}",
    response_model=EvalResultOut,
)
async def review_run_result(
    run_id: str,
    result_id: str,
    payload: EvalReviewUpdate,
    user: User = Depends(require_permission("eval:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> EvalResultOut:
    return await review_result(
        db,
        run_id=run_id,
        result_id=result_id,
        verdict=payload.verdict,
        note=payload.note.strip(),
        user=user,
    )
