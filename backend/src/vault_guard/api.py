"""FastAPI application — Vault Guard REST API."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from vault_guard.cache import TTLCache
from vault_guard.history import detect_grade_drop, get_history, init_db, record_grade
from vault_guard.models import SafetyGrade, ScoredVault
from vault_guard.risk_collector import collect_risks
from vault_guard.scanner import scan_vaults
from vault_guard.schemas import (
    GradeHistoryRecord,
    HealthResponse,
    RiskProfileSchema,
    SafeYieldResponse,
    ScoredVaultSchema,
    VaultHistoryResponse,
    VaultListResponse,
    VaultSchema,
)
from vault_guard.scorer import score_vaults
from vault_guard.yield_finder import find_safe_yields

logger = logging.getLogger(__name__)

_CACHE_TTL = 300.0  # 5 minutes
_DB_PATH = Path("data/vault_guard_history.db")

_cache: TTLCache = TTLCache(default_ttl=_CACHE_TTL)
_last_refresh: datetime | None = None
_refresh_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------


def _to_schema(sv: ScoredVault) -> ScoredVaultSchema:
    return ScoredVaultSchema(
        vault=VaultSchema(
            address=sv.vault.address,
            protocol=sv.vault.protocol,
            asset=sv.vault.asset,
            tvl_usd=sv.vault.tvl_usd,
            apy=sv.vault.apy,
            utilization_rate=sv.vault.utilization_rate,
        ),
        risk=RiskProfileSchema(
            utilization=sv.risk.utilization,
            tvl_change_7d=sv.risk.tvl_change_7d,
            oracle_risk_score=sv.risk.oracle_risk_score,
            audit_score=sv.risk.audit_score,
            drawdown_max=sv.risk.drawdown_max,
            sufficient_data=sv.risk.sufficient_data,
        ),
        score=sv.score,
        grade=sv.grade.value,
    )


async def _run_pipeline() -> list[ScoredVault]:
    """Scan → collect risks → score → persist history. Returns scored vaults."""
    global _last_refresh  # noqa: PLW0603
    async with httpx.AsyncClient() as client:
        vaults = await scan_vaults(client)
    risks = collect_risks(vaults)
    scored = score_vaults(vaults, risks, use_ml=False)

    # Persist history and flag drops
    init_db(_DB_PATH)
    for sv in scored:
        record_grade(sv.vault.address, sv.grade, sv.score, _DB_PATH)
        if detect_grade_drop(sv.vault.address, _DB_PATH):
            logger.warning("Grade drop detected for vault %s (%s)", sv.vault.address, sv.grade)

    _last_refresh = datetime.now(timezone.utc)
    return scored


async def _get_scored_vaults(force: bool = False) -> list[ScoredVault]:
    """Return scored vaults from cache or run the pipeline."""
    cached = _cache.get("scored_vaults")
    if cached is not None and not force:
        return cached

    async with _refresh_lock:
        # Double-check after acquiring lock
        cached = _cache.get("scored_vaults")
        if cached is not None and not force:
            return cached
        scored = await _run_pipeline()
        _cache.set("scored_vaults", scored)
        return scored


# ---------------------------------------------------------------------------
# Background refresh task
# ---------------------------------------------------------------------------


async def _background_refresh(interval: float = _CACHE_TTL) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            await _get_scored_vaults(force=True)
            logger.info("Background refresh complete — %s", _last_refresh)
        except Exception as exc:
            logger.error("Background refresh failed: %s", exc)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(_DB_PATH)
    # Warm cache on startup (best-effort)
    try:
        await _get_scored_vaults()
    except Exception as exc:
        logger.warning("Initial pipeline run failed: %s", exc)
    task = asyncio.create_task(_background_refresh())
    yield
    task.cancel()


# ---------------------------------------------------------------------------
# Logging middleware
# ---------------------------------------------------------------------------


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info("%s %s", request.method, request.url.path)
        response = await call_next(request)
        logger.info("%s %s → %d", request.method, request.url.path, response.status_code)
        return response


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="Base Vault Guard",
        description="AI-powered safety scoring for DeFi vaults on Base.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    async def health() -> HealthResponse:
        cached = _cache.get("scored_vaults") or []
        return HealthResponse(
            status="ok",
            vault_count=len(cached),
            last_refresh=_last_refresh,
        )

    @app.get("/vaults", response_model=VaultListResponse, tags=["vaults"])
    async def list_vaults(
        protocol: Annotated[str | None, Query(description="Filter by protocol")] = None,
        grade: Annotated[
            str | None, Query(description="Filter by safety grade (A/B/C/D/F)")
        ] = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> VaultListResponse:
        scored = await _get_scored_vaults()

        if protocol:
            scored = [sv for sv in scored if sv.vault.protocol.lower() == protocol.lower()]
        if grade:
            try:
                grade_filter = SafetyGrade(grade.upper())
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"Invalid grade '{grade}'. Use A/B/C/D/F."
                )
            scored = [sv for sv in scored if sv.grade == grade_filter]

        total = len(scored)
        start = (page - 1) * page_size
        page_items = scored[start : start + page_size]

        return VaultListResponse(
            items=[_to_schema(sv) for sv in page_items],
            total=total,
            page=page,
            page_size=page_size,
        )

    @app.get("/vaults/safe-yield", response_model=SafeYieldResponse, tags=["vaults"])
    async def safe_yield(
        min_grade: Annotated[
            str, Query(description="Minimum safety grade (A/B/C/D/F)")
        ] = "B",
    ) -> SafeYieldResponse:
        try:
            grade_enum = SafetyGrade(min_grade.upper())
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid grade '{min_grade}'. Use A/B/C/D/F."
            )
        scored = await _get_scored_vaults()
        filtered = find_safe_yields(scored, min_grade=grade_enum)
        return SafeYieldResponse(
            items=[_to_schema(sv) for sv in filtered],
            min_grade=grade_enum.value,
            total=len(filtered),
        )

    @app.get("/vaults/{address}/history", response_model=VaultHistoryResponse, tags=["vaults"])
    async def vault_history(address: str) -> VaultHistoryResponse:
        init_db(_DB_PATH)
        records = get_history(address, limit=30, db_path=_DB_PATH)
        return VaultHistoryResponse(
            vault_address=address,
            history=[
                GradeHistoryRecord(grade=r.grade.value, score=r.score, recorded_at=r.recorded_at)
                for r in records
            ],
        )

    @app.get("/vaults/{address}", response_model=ScoredVaultSchema, tags=["vaults"])
    async def vault_detail(address: str) -> ScoredVaultSchema:
        scored = await _get_scored_vaults()
        match = next((sv for sv in scored if sv.vault.address.lower() == address.lower()), None)
        if match is None:
            raise HTTPException(status_code=404, detail=f"Vault '{address}' not found.")
        return _to_schema(match)

    return app


app = create_app()
