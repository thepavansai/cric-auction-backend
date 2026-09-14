# 🏏 Cricket Auction Backend

A high-performance, thread-safe FastAPI backend for real-time IPL-style cricket auctions, migrated from Go to Python.

Designed to work seamlessly with the [cric-auction-frontend](https://github.com/thepavansai/cric-auction-frontend) React frontend.

---

## ⚡ Features

- **Dynamic Configuration (`/api/set-config`):** Configure teams, budgets, purse amounts, image folders, and captains on the fly.
- **Bidding Engine (`/api/bid`):** Real-time bidding with team budget deduction, duplicate-sale protection, and force-sell overrides (`ignore_budget`).
- **Undo / Reverse Bid (`/api/reverse-bid`):** Roll back bids in LIFO order, automatically refunding the team's purse and returning the player to unsold status.
- **Dynamic Image Serving (`/images/{filename}`):** Streams player photos dynamically from the user-configured image path, secured against path traversal attacks.
- **Normalized Alphanumeric Player IDs:** Accepts standard string player IDs (e.g. `P101`, `EMP-42`, `C01`).
- **Thread-Safe State:** Synchronized using `threading.RLock` to prevent race conditions across concurrent AnyIO worker threads.
- **Flexible CORS:** Supports any localhost port (`3000`, `5173`, `5174`, etc.) and production GitHub Pages deployments out-of-the-box.

---

## 🛠️ Tech Stack

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/)
- **Data Validation:** [Pydantic v2](https://docs.pydantic.dev/)
- **Server:** [Uvicorn](https://www.uvicorn.org/)
- **Package & Project Manager:** [uv](https://github.com/astral-sh/uv) (Preferred)
- **Runtime:** Python 3.13+

---

## 🚀 Getting Started

### Prerequisites

Install [uv](https://docs.astral.sh/uv/) (recommended):
```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

### Quickstart with `uv` (Recommended)

1. Clone the repository:
   ```bash
   git clone git@github.com:thepavansai/cric-auction-backend.git
   cd cric-auction-backend
   ```

2. Install dependencies and sync virtual environment:
   ```bash
   uv sync
   ```

3. Run the development server on port `8080`:
   ```bash
   uv run uvicorn cric_auction_backend.main:app --host 0.0.0.0 --port 8080 --reload
   ```

---

### Alternative: Standard Python `venv` & `pip`

<details>
<summary>Click to view standard pip setup</summary>

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -e .

# 3. Start server
uvicorn cric_auction_backend.main:app --host 0.0.0.0 --port 8080 --reload
```
</details>

---

## 📖 API Documentation

Once the server is running, visit:
- **Interactive Swagger UI:** [http://localhost:8080/docs](http://localhost:8080/docs)
- **ReDoc:** [http://localhost:8080/redoc](http://localhost:8080/redoc)

### Key Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Health check endpoint |
| `POST` | `/api/set-config` | Initializes teams, base budget, and image directory |
| `GET` | `/api/teams` | Retrieves the current list of teams, remaining budgets, and rosters |
| `POST` | `/api/bid` | Submits a winning bid for a player |
| `POST` | `/api/reverse-bid` | Reverses the last bid, restoring team budget and player state |
| `GET` | `/images/{filename}` | Dynamically serves player photos |

---

### Example Payloads

#### 1. Set Auction Config (`POST /api/set-config`)
```json
{
  "image_path": "/path/to/player_photos",
  "teams": ["Super Kings", "Mumbai Indians", "Royal Challengers"],
  "base_purse": 10000000,
  "captain_ids": ["P101", "P102"],
  "captain_names": ["Virat Kohli", "Rohit Sharma"]
}
```

#### 2. Place Bid (`POST /api/bid`)
```json
{
  "team_id": "t1",
  "player_id": "P101",
  "bid_amount": 2500000,
  "ignore_budget": false
}
```

#### 3. Reverse Bid (`POST /api/reverse-bid`)
*No request body required.* Returns the reverted bid and updated purse:
```json
{
  "status": "ok",
  "team_id": "t1",
  "player_id": "P101",
  "bid_amount": 2500000,
  "remaining_budget": 10000000
}
```

---

## 📂 Project Structure

```
cric-auction-backend/
├── pyproject.toml              # Dependencies and project metadata
├── uv.lock                     # Deterministic dependency tree locked by uv
├── README.md                   # Project documentation
└── src/
    └── cric_auction_backend/
        ├── __init__.py
        ├── main.py             # FastAPI routes, CORS, and dynamic image proxy
        ├── models.py           # Pydantic schemas (Team, Bid, Config)
        └── state.py            # Thread-safe in-memory application state
```

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -m 'feat: add some feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License.
