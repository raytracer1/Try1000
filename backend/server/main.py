"""Try1000 Backend — FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from server.database import init_db
from server.api import auth, teams, tactics, simulation, analytics, agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Try1000 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Set-Cookie"],
)

# Mount routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(teams.router, prefix="/api/v1/teams", tags=["teams"])
app.include_router(tactics.router, prefix="/api/v1/tactics", tags=["tactics"])
app.include_router(simulation.router, prefix="/api/v1", tags=["simulation"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["agent"])


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


# ─── Alibaba Cloud FC handler ───
# FC HTTP trigger → Mangum → FastAPI ASGI

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    handler = None  # local dev uses uvicorn directly
