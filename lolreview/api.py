from fastapi import FastAPI
from fastapi.responses import JSONResponse

from lolreview.schemas import ErrorResponse, Health, ModelMetrics, PlayerGames, Review

app = FastAPI(title="LeagueVODreview")

_NOT_IMPLEMENTED = {501: {"model": ErrorResponse}}


def _not_implemented() -> JSONResponse:
    body = ErrorResponse.model_validate(
        {"error": {"code": "not_implemented", "message": "Not implemented yet."}}
    )
    return JSONResponse(status_code=501, content=body.model_dump(mode="json"))


@app.get("/api/health", response_model=Health, responses=_NOT_IMPLEMENTED)
def health():
    return _not_implemented()


@app.get(
    "/api/player/{platform}/{name}/{tag}",
    response_model=PlayerGames,
    responses=_NOT_IMPLEMENTED,
)
def player(platform: str, name: str, tag: str, start: int = 0, count: int = 10):
    return _not_implemented()


@app.get("/api/review/{match_id}", response_model=Review, responses=_NOT_IMPLEMENTED)
def review(match_id: str, p: int):
    return _not_implemented()


@app.get("/api/model", response_model=ModelMetrics, responses=_NOT_IMPLEMENTED)
def model():
    return _not_implemented()
