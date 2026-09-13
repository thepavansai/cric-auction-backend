import os
import uvicorn


def main() -> None:
  """Run the Cricket Auction FastAPI server."""
  # Allows overriding via environment variables, defaulting to 0.0.0.0:8080
  host = os.getenv("HOST", "0.0.0.0")
  port = int(os.getenv("PORT", "8080"))
  reload = os.getenv("RELOAD", "true").lower() in ("true", "1", "yes")

  uvicorn.run(
      "cric_auction_backend.main:app",
      host=host,
      port=port,
      reload=reload,
  )


if __name__ == "__main__":
  main()