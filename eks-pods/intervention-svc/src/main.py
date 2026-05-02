"""intervention-svc · 승인 · 실행 단일 창구.

V6.3 MSA Pod #5. order_approvals + returns 승인 처리. pending_orders 상태 전이.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import close_pool, init_pool
from .routes.intervention import router as intervention_router
from .settings import settings

logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    yield
    close_pool()


app = FastAPI(title="bookflow-intervention-svc", version="0.1.0", lifespan=lifespan)
app.include_router(intervention_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "intervention-svc"}
