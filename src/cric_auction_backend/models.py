import math

from pydantic import BaseModel, Field, field_validator


MAX_AUCTION_AMOUNT = 1_000_000.0


def _validate_money(
    value: float,
    *,
    require_one_decimal: bool = True,
    enforce_maximum: bool = True,
) -> float:
    if not math.isfinite(value):
        raise ValueError("amount must be finite")
    if value <= 0 or (enforce_maximum and value > MAX_AUCTION_AMOUNT):
        raise ValueError(f"amount must be greater than zero and at most {MAX_AUCTION_AMOUNT}")
    if require_one_decimal and not math.isclose(value * 10, round(value * 10), abs_tol=1e-9):
        raise ValueError("amount must have at most one decimal place")
    return value


class Team(BaseModel):
    id: str
    name: str
    budget: float
    roster: list[str] = Field(default_factory=list)


class AuctionConfig(BaseModel):
    image_path: str = ""
    teams: list[str] = Field(min_length=1)
    base_purse: float
    captain_ids: list[str] = Field(default_factory=list)
    captain_names: list[str] = Field(default_factory=list)

    @field_validator("teams")
    @classmethod
    def validate_teams(cls, teams: list[str]) -> list[str]:
        normalized = [team.strip() for team in teams]
        if any(not team for team in normalized):
            raise ValueError("team names cannot be blank")
        if len({team.casefold() for team in normalized}) != len(normalized):
            raise ValueError("team names must be unique")
        return normalized

    @field_validator("base_purse")
    @classmethod
    def validate_base_purse(cls, value: float) -> float:
        return _validate_money(value)


class BidRequest(BaseModel):
    team_id: str
    player_id: str
    bid_amount: float
    ignore_budget: bool = False
    request_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("bid_amount")
    @classmethod
    def validate_bid_amount(cls, value: float) -> float:
        return _validate_money(value)


class BidHistory(BaseModel):
    team_id: str
    player_id: str
    bid_amount: float

    @field_validator("bid_amount")
    @classmethod
    def validate_historical_bid(cls, value: float) -> float:
        return _validate_money(value, require_one_decimal=False, enforce_maximum=False)


class ReverseBidRequest(BaseModel):
    request_id: str | None = Field(default=None, min_length=1, max_length=128)
    expected_player_id: str | None = None


class StatusResponse(BaseModel):
    status: str


class BidResponse(BaseModel):
    status: str
    remaining_budget: float


class ReverseBidResponse(BaseModel):
    status: str
    team_id: str
    player_id: str
    bid_amount: float
    remaining_budget: float
