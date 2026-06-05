"""FastAPI app wiring — single process, four logically independent routers."""
from __future__ import annotations

from importlib import resources

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from nanda.routers import demo, facts, index, resolver


def create_app() -> FastAPI:
    app = FastAPI(
        title="NANDA Agent Business Card Resolver (POC)",
        version="0.1.0",
        description=(
            "Resolves handles like `@acme:support/billing-bot` to a verified "
            "endpoint + capability list via signed AgentFacts (Ed25519 + URDNA2015)."
        ),
    )
    app.include_router(index.router)
    app.include_router(facts.router)
    app.include_router(resolver.router)
    app.include_router(demo.router)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def root() -> HTMLResponse:
        html = resources.files("nanda.ui").joinpath("index.html").read_text()
        return HTMLResponse(html)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
