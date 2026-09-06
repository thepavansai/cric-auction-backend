import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
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
        "https://thepavansai.github.io",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
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

        team.budget += last_bid.bid_amount

        # Remove player from roster (pop last if matches, else linear remove)
        if team.roster and team.roster[-1] == last_bid.player_id:
            team.roster.pop()
        elif last_bid.player_id in team.roster:
            team.roster.remove(last_bid.player_id)

        state.bid_history.pop()

        return ReverseBidResponse(
            status="ok",
            team_id=last_bid.team_id,
            player_id=last_bid.player_id,
            bid_amount=last_bid.bid_amount,
            remaining_budget=team.budget,
        )
@app.get("/images/{filename:path}")
def get_image(filename:str):
    if not state.image_path:
        raise HTTPException(
            status_code=503,
            detail="Image directory isn't configured",
        )
    safe_base = os.path.abspath(state.image_path)
    target_path = os.path.abspath(os.path.join(safe_base,filename))

    if not target_path.startswith(safe_base) or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid path")

    if not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(target_path)
