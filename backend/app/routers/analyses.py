"""Analysis and analysis-run management router."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.ai_config import AIConfig
from app.models.analysis import Analysis, AnalysisRun
from app.models.spotify_account import SpotifyAccount
from app.models.user import User
from app.schemas.analysis import AnalysisCreate, AnalysisRead, AnalysisRunRead, AnalysisUpdate
from app.services import analysis_service

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


# ── Analyses ──────────────────────────────────────────────────────────────────


@router.post("", response_model=AnalysisRead, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    body: AnalysisCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Analysis:
    """Create a new analysis configuration."""
    # Verify the Spotify account belongs to this user
    account = await db.get(SpotifyAccount, body.spotify_account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spotify account not found",
        )
    # Verify the AI config belongs to this user
    ai_config = await db.get(AIConfig, body.ai_config_id)
    if ai_config is None or ai_config.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI config not found",
        )

    analysis = Analysis(
        user_id=user.id,
        spotify_account_id=body.spotify_account_id,
        ai_config_id=body.ai_config_id,
        name=body.name,
        prompt=body.prompt,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis


@router.get("", response_model=list[AnalysisRead])
async def list_analyses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Analysis]:
    """Return all analyses belonging to the authenticated user."""
    result = await db.execute(select(Analysis).where(Analysis.user_id == user.id))
    return list(result.scalars().all())


@router.patch("/{analysis_id}", response_model=AnalysisRead)
async def update_analysis(
    analysis_id: uuid.UUID,
    body: AnalysisUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Analysis:
    """Update an analysis name and/or prompt."""
    analysis = await db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found"
        )
    if analysis.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this analysis",
        )
    if body.name is not None:
        analysis.name = body.name
    if body.prompt is not None:
        analysis.prompt = body.prompt
    await db.commit()
    await db.refresh(analysis)
    return analysis


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_analysis(
    analysis_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an analysis. Returns 403 if not owned by the user."""
    analysis = await db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found"
        )
    if analysis.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this analysis",
        )
    await db.delete(analysis)
    await db.commit()


# ── Analysis runs ─────────────────────────────────────────────────────────────


@router.post(
    "/{analysis_id}/run",
    response_model=AnalysisRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_run(
    analysis_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisRun:
    """Trigger an immediate analysis run. Returns the run record."""
    analysis = await db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found"
        )
    if analysis.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to run this analysis",
        )
    run = await analysis_service.run_analysis(db, analysis_id)
    return run


@router.get("/{analysis_id}/runs", response_model=list[AnalysisRunRead])
async def list_runs(
    analysis_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AnalysisRun]:
    """Return all runs for a given analysis."""
    analysis = await db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found"
        )
    if analysis.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view these runs",
        )
    result = await db.execute(
        select(AnalysisRun).where(AnalysisRun.analysis_id == analysis_id)
    )
    return list(result.scalars().all())


@router.get("/{analysis_id}/runs/{run_id}", response_model=AnalysisRunRead)
async def get_run(
    analysis_id: uuid.UUID,
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisRun:
    """Return a single run result."""
    analysis = await db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found"
        )
    if analysis.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this run",
        )
    run = await db.get(AnalysisRun, run_id)
    if run is None or run.analysis_id != analysis_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )
    return run
