import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .journal import AuctionJournal, JournalError
from .models import (
    AuctionConfig,
    BidHistory,
    BidRequest,
    BidResponse,
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

        if request.player_id in state.expert_ids and not request.ignore_budget:
            expert_count = sum(player_id in state.expert_ids for player_id in team.roster)
            if expert_count >= state.max_experts_per_team:
                raise HTTPException(
                    status_code=403,
                    detail=f"{team.name} has reached its limit of {state.max_experts_per_team} experts",
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
            journal.append_bid(bid)
        except JournalError as exc:
            raise HTTPException(
                status_code=503,
                detail="Auction state could not be persisted",
            ) from exc
        return state.apply_bid(bid)


@app.post("/api/reverse-bid", response_model=ReverseBidResponse)
def reverse_bid():
    with state.lock:
        if not state.bid_history:
            raise HTTPException(
                status_code=409,
                detail="No previous bid to reverse",
            )

        last_bid = state.bid_history[-1]
        team = state.teams.get(last_bid.team_id)

        if team is None:
            raise HTTPException(
                status_code=404,
                detail="Team not found",
            )

        if team.budget + last_bid.bid_amount < 0:
            raise HTTPException(
                status_code=409,
                detail="Invalid bid reversal",
            )

        try:
            journal.append_reverse()
        except JournalError as exc:
            raise HTTPException(
                status_code=503,
                detail="Auction state could not be persisted",
            ) from exc
        return state.apply_reverse()
@app.get("/images/{filename:path}")
def get_image(filename:str):
    if not state.image_path:
        raise HTTPException(
            status_code=503,
            detail="Image directory isn't configured",
        )
    safe_base = os.path.abspath(state.image_path)
    target_path = os.path.abspath(os.path.join(safe_base,filename))

    if os.path.commonpath([safe_base, target_path]) != safe_base or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid path")

    if not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(target_path)
