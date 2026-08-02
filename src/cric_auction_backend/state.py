from .models import BidHistory, Team


class AppState:
    def __init__(self):
        # Teams indexed by team ID (e.g. "t1", "t2")
        self.teams: dict[str, Team] = {}

        # Maintains insertion order for returning teams
        self.team_order: list[str] = []

        # Stack of successful bids (used for reverse bid)
        self.bid_history: list[BidHistory] = []

        # Auction configuration
        self.image_path: str = ""
        self.base_purse: float = 0
        self.captain_ids: list[int] = []
        self.captain_names: list[str] = []


state = AppState()
