import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .models import AuctionConfig, BidHistory
from .state import AppState


JOURNAL_VERSION = 1


class JournalError(RuntimeError):
    pass


class AuctionJournal:
    def __init__(self, path: str | Path | None = None):
        configured_path = path or os.getenv("AUCTION_JOURNAL_PATH", "auction-state.jsonl")
        self.path = Path(configured_path)
        self._append_healthy = True

    def replace_config(self, config: AuctionConfig) -> None:
        record = self._encode("config", config.model_dump())
        temp_path: Path | None = None

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            file_descriptor, raw_temp_path = tempfile.mkstemp(
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
            )
            temp_path = Path(raw_temp_path)
            with os.fdopen(file_descriptor, "wb") as stream:
                stream.write(record)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self.path)
            self._append_healthy = True
        except OSError as exc:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise JournalError(f"Could not persist auction config: {exc}") from exc

    def append_bid(
        self,
        bid: BidHistory,
        request_id: str | None = None,
        ignore_budget: bool = False,
    ) -> None:
        data: dict[str, Any] = {"bid": bid.model_dump()}
        if request_id:
            data["request_id"] = request_id
            data["ignore_budget"] = ignore_budget
        self._append(self._encode("bid", data))

    def append_reverse(self, request_id: str | None = None) -> None:
        data = {"request_id": request_id} if request_id else None
        self._append(self._encode("reverse", data))

    def restore_into(self, target: AppState) -> None:
        restored = AppState()
        if not self.path.exists():
            with target.lock:
                target.replace_with(restored)
            return

        try:
            raw_journal = self.path.read_bytes()
            complete_length = raw_journal.rfind(b"\n") + 1
            if complete_length < len(raw_journal):
                with self.path.open("r+b") as stream:
                    stream.truncate(complete_length)
                    stream.flush()
                    os.fsync(stream.fileno())
                raw_journal = raw_journal[:complete_length]

            configured = False
            for line_number, raw_record in enumerate(raw_journal.splitlines(), start=1):
                event = json.loads(raw_record)
                event_type, event_data = self._validate_event(event, line_number)

                if event_type == "config":
                    if configured:
                        raise JournalError("Journal contains more than one config record")
                    restored.configure(AuctionConfig.model_validate(event_data))
                    configured = True
                elif not configured:
                    raise JournalError("Journal event appears before its config record")
                elif event_type == "bid":
                    bid_data = event_data.get("bid", event_data)
                    restored.apply_bid(
                        BidHistory.model_validate(bid_data),
                        event_data.get("request_id"),
                        bool(event_data.get("ignore_budget", False)),
                    )
                else:
                    restored.apply_reverse(
                        event_data.get("request_id") if event_data else None
                    )
        except JournalError:
            raise
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise JournalError(f"Could not restore auction journal: {exc}") from exc

        with target.lock:
            target.replace_with(restored)
        self._append_healthy = True

    def _append(self, record: bytes) -> None:
        if not self._append_healthy:
            raise JournalError(
                "Journal requires startup repair or a new auction config"
            )

        original_size = 0
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                original_size = self.path.stat().st_size
            with self.path.open("ab") as stream:
                bytes_written = stream.write(record)
                if bytes_written != len(record):
                    raise OSError("Incomplete journal write")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            try:
                with self.path.open("r+b") as stream:
                    stream.truncate(original_size)
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError:
                self._append_healthy = False
            raise JournalError(f"Could not append auction event: {exc}") from exc

    @staticmethod
    def _encode(event_type: str, data: dict[str, Any] | None = None) -> bytes:
        event: dict[str, Any] = {
            "version": JOURNAL_VERSION,
            "type": event_type,
        }
        if data is not None:
            event["data"] = data
        return (json.dumps(event, separators=(",", ":")) + "\n").encode("utf-8")

    @staticmethod
    def _validate_event(
        event: Any,
        line_number: int,
    ) -> tuple[str, dict[str, Any] | None]:
        if not isinstance(event, dict) or event.get("version") != JOURNAL_VERSION:
            raise JournalError(f"Unsupported journal record at line {line_number}")

        event_type = event.get("type")
        if event_type not in {"config", "bid", "reverse"}:
            raise JournalError(f"Unknown journal event at line {line_number}")

        event_data = event.get("data")
        if event_type in {"config", "bid"} and not isinstance(event_data, dict):
            raise JournalError(f"Missing journal data at line {line_number}")
        if event_type == "reverse" and event_data is not None and not isinstance(event_data, dict):
            raise JournalError(f"Invalid reversal data at line {line_number}")
        return event_type, event_data