import os
import math
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .journal import AuctionJournal, JournalError
from .models import (
    AuctionConfig,
    BidHistory,
    BidRequest,
    BidResponse,
    ReverseBidRequest,
    ReverseBidResponse,
    StatusResponse,
    Team,
)
from .state import state

journal = AuctionJournal()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    journal.restore_into(state)
    yield


app = FastAPI(lifespan=lifespan)


def _safe_validation_value(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _safe_validation_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_validation_value(item) for item in value]
    if isinstance(value, BaseException):
        return str(value)
    return value


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": _safe_validation_value(exc.errors())},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://thepavansai.github.io",
        "https://pavansai.is-a.dev",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$|^https://.*\.pages\.dev$|^https://.*\.workers\.dev$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def read_root():
    return {"message": "I'm Batman"}


@app.post("/api/set-config", response_model=StatusResponse)
def set_config(request: AuctionConfig):
    with state.lock:
        if request.image_path:
            image_root_value = os.getenv("AUCTION_IMAGE_ROOT")
            if image_root_value:
                image_root = Path(image_root_value).resolve()
                image_directory = Path(request.image_path).resolve()
                if not image_directory.is_dir() or not image_directory.is_relative_to(image_root):
                    raise HTTPException(
                        status_code=400,
                        detail="Image directory must exist under the configured image root",
                    )
        try:
            journal.replace_config(request)
        except JournalError as exc:
            raise HTTPException(
                status_code=503,
                detail="Auction state could not be persisted",
            ) from exc
        state.configure(request)

    return StatusResponse(status="ok")


@app.get("/api/teams", response_model=list[Team])
def get_teams():
    with state.lock:
        teams = []
        for team_id in state.team_order:
            teams.append(state.teams[team_id])
        return teams


@app.post("/api/bid", response_model=BidResponse)
def place_bid(request: BidRequest):
    with state.lock:
        if request.request_id:
            previous_request = state.bid_requests.get(request.request_id)
            if previous_request:
                fingerprint, response = previous_request
                incoming_fingerprint = (
                    request.team_id,
                    request.player_id,
                    request.bid_amount,
                    request.ignore_budget,
                )
                if fingerprint != incoming_fingerprint:
                    raise HTTPException(
                        status_code=409,
                        detail="Request ID was already used for a different bid",
                    )
                return response

        if not request.player_id.strip():
            raise HTTPException(status_code=400, detail="player_id is required")

        team = state.teams.get(request.team_id)

        if team is None:
            raise HTTPException(
                status_code=404,
                detail="Team not found",
            )

        if request.bid_amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Bid amount must be greater than zero",
            )

        for team_itr in state.teams.values():
            if request.player_id in team_itr.roster:
                raise HTTPException(
                    status_code=409,
                    detail="Player already sold",
                )

        if request.bid_amount > team.budget and not request.ignore_budget:
            raise HTTPException(
                status_code=403,
                detail="Insufficient budget",
            )

        bid = BidHistory(
            team_id=request.team_id,
            player_id=request.player_id,
            bid_amount=request.bid_amount,
        )
        try:
            journal.append_bid(bid, request.request_id, request.ignore_budget)
        except JournalError as exc:
            raise HTTPException(
                status_code=503,
                detail="Auction state could not be persisted",
            ) from exc
        return state.apply_bid(bid, request.request_id, request.ignore_budget)


@app.post("/api/reverse-bid", response_model=ReverseBidResponse)
def reverse_bid(request: ReverseBidRequest | None = None):
    with state.lock:
        request_id = request.request_id if request else None
        expected_player_id = request.expected_player_id if request else None
        if request_id:
            previous_request = state.reverse_requests.get(request_id)
            if previous_request:
                previous_player_id, response = previous_request
                if previous_player_id != expected_player_id:
                    raise HTTPException(
                        status_code=409,
                        detail="Request ID was already used for a different reversal",
                    )
                return response

        if not state.bid_history:
            raise HTTPException(
                status_code=409,
                detail="No previous bid to reverse",
            )

        last_bid = state.bid_history[-1]
        if expected_player_id and expected_player_id != last_bid.player_id:
            raise HTTPException(
                status_code=409,
                detail="Latest bid changed; refresh before reversing",
            )
        team = state.teams.get(last_bid.team_id)

        if team is None:
            raise HTTPException(
                status_code=404,
                detail="Team not found",
            )

        try:
            journal.append_reverse(request_id)
        except JournalError as exc:
            raise HTTPException(
                status_code=503,
                detail="Auction state could not be persisted",
            ) from exc
        return state.apply_reverse(request_id)


@app.get("/images/{filename:path}")
def get_image(filename: str):
    if not state.image_path:
        raise HTTPException(
            status_code=503,
            detail="Image directory isn't configured",
        )
    image_root_value = os.getenv("AUCTION_IMAGE_ROOT")
    if not image_root_value:
        raise HTTPException(status_code=503, detail="Image root is not configured")

    image_root = Path(image_root_value).resolve()
    safe_base = Path(state.image_path).resolve()
    target_path = (safe_base / filename).resolve()
    if (
        not safe_base.is_relative_to(image_root)
        or not target_path.is_relative_to(safe_base)
        or target_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    ):
        raise HTTPException(status_code=400, detail="Invalid path")

    if not target_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(target_path)
