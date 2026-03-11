"""FastAPI server — serves analysis results to the frontend."""

from __future__ import annotations

import argparse
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .analyze import analyze_repo

app = FastAPI(title="ArchLens Analyzer", version="0.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache: repo_path -> result dict
_cache: dict[str, dict] = {}


@app.get("/api/analyze")
def api_analyze(path: str = Query(..., description="Path to the repository to analyze")):
    """Analyze a repository and return the graph data."""
    repo = Path(path).resolve()
    if not repo.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

    cache_key = str(repo)
    if cache_key not in _cache:
        try:
            result = analyze_repo(repo)
            _cache[cache_key] = result.to_dict()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse(_cache[cache_key])


@app.post("/api/analyze/clear")
def api_clear_cache():
    """Clear the analysis cache."""
    _cache.clear()
    return {"status": "ok"}


@app.get("/api/health")
def api_health():
    return {"status": "ok"}


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="ArchLens Analyzer Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    uvicorn.run(
        "archlens.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
