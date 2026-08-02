from pydantic import BaseModel, Field


class Team(BaseModel):
    id: str
    name: str
    budget: float
    roster: list[int] = Field(default_factory=list)


class AuctionConfig(BaseModel):
    image_path: str = ""
    teams: list[str] = Field(default_factory=list)
    base_purse: float
    captain_ids: list[int] = Field(default_factory=list)
    captain_names: list[str] = Field(default_factory=list)


class BidRequest(BaseModel):
    team_id: str
    player_id: int
    bid_amount: float
    ignore_budget: bool = False


class BidHistory(BaseModel):
    team_id: str
    player_id: int
    bid_amount: float


class StatusResponse(BaseModel):
    status: str


class BidResponse(BaseModel):
    status: str
    remaining_budget: float


class ReverseBidResponse(BaseModel):
    status: str
    team_id: str
    player_id: int
    bid_amount: float
    remaining_budget: float
