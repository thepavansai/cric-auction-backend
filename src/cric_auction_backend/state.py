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
        self.bid_requests: dict[str, tuple[tuple[str, str, float, bool], BidResponse]] = {}
        self.reverse_requests: dict[str, tuple[str | None, ReverseBidResponse]] = {}

        # Auction configuration
        self.image_path: str = ""
        self.base_purse: float = 0
        self.captain_ids: list[str] = []
        self.captain_names: list[str] = []

    def configure(self, config: AuctionConfig) -> None:
        self.teams.clear()
        self.team_order.clear()
        self.bid_history.clear()
        self.bid_requests.clear()
        self.reverse_requests.clear()

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
            raise ValueError(f"Player already sold in journal: {bid.player_id}")

        team.budget = round(team.budget - bid.bid_amount, 1)
        team.roster.append(bid.player_id)
        self.bid_history.append(bid)
        response = BidResponse(status="ok", remaining_budget=team.budget)
        if request_id:
            fingerprint = (bid.team_id, bid.player_id, bid.bid_amount, ignore_budget)
            self.bid_requests[request_id] = (fingerprint, response)
        return response

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
        if team.roster[-1] == last_bid.player_id:
            team.roster.pop()
        else:
            team.roster.remove(last_bid.player_id)
        self.bid_history.pop()
        response = ReverseBidResponse(
            status="ok",
            team_id=last_bid.team_id,
            player_id=last_bid.player_id,
            bid_amount=last_bid.bid_amount,
            remaining_budget=team.budget,
        )
        if request_id:
            self.reverse_requests[request_id] = (last_bid.player_id, response)
        return response

    def replace_with(self, restored: "AppState") -> None:
        self.teams = restored.teams
        self.team_order = restored.team_order
        self.bid_history = restored.bid_history
        self.bid_requests = restored.bid_requests
        self.reverse_requests = restored.reverse_requests
        self.image_path = restored.image_path
        self.base_purse = restored.base_purse
        self.captain_ids = restored.captain_ids
        self.captain_names = restored.captain_names


state = AppState()
