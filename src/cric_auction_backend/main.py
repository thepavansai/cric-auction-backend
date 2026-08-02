from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://thepavansai.github.io",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def read_root():
    return {"message": "I'm Batman"}


@app.post("/api/set-config", response_model=StatusResponse)
def set_config(request: AuctionConfig):
    state.teams.clear()
    state.team_order.clear()
    state.bid_history.clear()
    state.image_path = ""

    for index, team_name in enumerate(request.teams, start=1):
        team_id = f"t{index}"

        team = Team(
            id=team_id,
            name=team_name,
            budget=request.base_purse,
            roster=[],
        )

        state.teams[team_id] = team
        state.team_order.append(team_id)

    state.image_path = request.image_path
    state.base_purse = request.base_purse
    state.captain_ids = request.captain_ids
    state.captain_names = request.captain_names

    return StatusResponse(status="ok")


@app.get("/api/teams", response_model=list[Team])
def get_teams():
    teams = []

    for team_id in state.team_order:
        teams.append(state.teams[team_id])

    return teams


@app.post("/api/bid", response_model=BidResponse)
def place_bid(request: BidRequest):
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

    team.budget -= request.bid_amount
    team.roster.append(request.player_id)

    state.bid_history.append(
        BidHistory(
            team_id=request.team_id,
            player_id=request.player_id,
            bid_amount=request.bid_amount,
        )
    )

    return BidResponse(
        status="ok",
        remaining_budget=team.budget,
    )
