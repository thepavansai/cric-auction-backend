import threading

from .models import (
    AuctionConfig,
    BidHistory,
    BidResponse,
    ReverseBidResponse,
    Team,
)


class AppState:
    def __init__(self):
        # Mutex lock to guard state modifications across AnyIO worker threads
        self.lock = threading.RLock()

        # Teams indexed by team ID (e.g. "t1", "t2")
        self.teams: dict[str, Team] = {}

        # Maintains insertion order for returning teams
        self.team_order: list[str] = []

        # Stack of successful bids (used for reverse bid)
        self.bid_history: list[BidHistory] = []

        # Auction configuration
        self.image_path: str = ""
        self.base_purse: float = 0
        self.max_experts_per_team: int = 3
        self.expert_ids: set[str] = set()
        self.captain_ids: list[str] = []
        self.captain_names: list[str] = []

    def configure(self, config: AuctionConfig) -> None:
        self.teams.clear()
        self.team_order.clear()
        self.bid_history.clear()

        for index, team_name in enumerate(config.teams, start=1):
            team_id = f"t{index}"
            self.teams[team_id] = Team(
                id=team_id,
                name=team_name,
                budget=config.base_purse,
                roster=[],
            )
            self.team_order.append(team_id)

        self.image_path = config.image_path
        self.base_purse = config.base_purse
        self.max_experts_per_team = config.max_experts_per_team
        self.expert_ids = set(config.expert_ids)
        self.captain_ids = list(config.captain_ids)
        self.captain_names = list(config.captain_names)

    def apply_bid(
        self,
        bid: BidHistory,
        request_id: str | None = None,
        ignore_budget: bool = False,
    ) -> BidResponse:
        team = self.teams.get(bid.team_id)
        if team is None:
            raise ValueError(f"Unknown team in bid: {bid.team_id}")
        if any(bid.player_id in item.roster for item in self.teams.values()):
            raise ValueError(f"Player already sold: {bid.player_id}")

        # Re-round: repeated float arithmetic drifts (e.g. 100 - 2.1 - 2.2)
        team.budget = round(team.budget - bid.bid_amount, 1)
        team.roster.append(bid.player_id)
        self.bid_history.append(bid)
        return BidResponse(status="ok", remaining_budget=team.budget)

    def apply_reverse(self, request_id: str | None = None) -> ReverseBidResponse:
        if not self.bid_history:
            raise ValueError("Cannot reverse an empty bid history")

        last_bid = self.bid_history[-1]
        team = self.teams.get(last_bid.team_id)
        if team is None:
            raise ValueError(f"Unknown team in reversal: {last_bid.team_id}")
        if last_bid.player_id not in team.roster:
            raise ValueError(f"Player missing during reversal: {last_bid.player_id}")

        team.budget = round(team.budget + last_bid.bid_amount, 1)
        # Remove player from roster (pop last if matches, else linear remove)
        if team.roster[-1] == last_bid.player_id:
            team.roster.pop()
        else:
            team.roster.remove(last_bid.player_id)
        self.bid_history.pop()
        return ReverseBidResponse(
            status="ok",
            team_id=last_bid.team_id,
            player_id=last_bid.player_id,
            bid_amount=last_bid.bid_amount,
            remaining_budget=team.budget,
        )

    def replace_with(self, restored: "AppState") -> None:
        self.teams = restored.teams
        self.team_order = restored.team_order
        self.bid_history = restored.bid_history
        self.image_path = restored.image_path
        self.base_purse = restored.base_purse
        self.max_experts_per_team = restored.max_experts_per_team
        self.expert_ids = restored.expert_ids
        self.captain_ids = restored.captain_ids
        self.captain_names = restored.captain_names


state = AppState()
