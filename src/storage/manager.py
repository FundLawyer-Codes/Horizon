"""Storage manager for configuration and state persistence."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from ..models import Config, SeenItemsData, SeenItem, ContentItem


class StorageManager:
    """Manages file-based storage for configuration and state."""

    def __init__(self, data_dir: str = "data"):
        """Initialize storage manager.

        Args:
            data_dir: Base directory for all data files
        """
        self.data_dir = Path(data_dir)
        self.config_path = self.data_dir / "config.json"
        self.seen_path = self.data_dir / "seen.json"
        self.summaries_dir = self.data_dir / "summaries"

        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)

    def load_config(self) -> Config:
        """Load configuration from config.json.

        Returns:
            Config: Parsed configuration object

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValidationError: If config format is invalid
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please create it based on the template in README.md"
            )

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Config.model_validate(data)

    def load_seen_items(self) -> SeenItemsData:
        """Load seen items tracking data.

        Returns:
            SeenItemsData: Seen items data, or empty if file doesn't exist
        """
        if not self.seen_path.exists():
            return SeenItemsData()

        with open(self.seen_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Parse datetime strings
        if data.get("last_run"):
            data["last_run"] = datetime.fromisoformat(data["last_run"].replace("Z", "+00:00"))

        for item_id, item_data in data.get("items", {}).items():
            item_data["first_seen"] = datetime.fromisoformat(
                item_data["first_seen"].replace("Z", "+00:00")
            )

        return SeenItemsData.model_validate(data)

    def save_seen_items(self, seen_data: SeenItemsData) -> None:
        """Save seen items tracking data atomically.

        Args:
            seen_data: Seen items data to save
        """
        # Prepare data with datetime serialization
        data = seen_data.model_dump(mode="json")

        # Convert datetime objects to ISO format
        if data.get("last_run"):
            data["last_run"] = data["last_run"].replace("+00:00", "Z")

        for item_id, item_data in data.get("items", {}).items():
            item_data["first_seen"] = item_data["first_seen"].replace("+00:00", "Z")

        # Atomic write: write to temp file, then rename
        temp_path = self.seen_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        temp_path.replace(self.seen_path)

    def is_item_seen(self, item_id: str, seen_data: SeenItemsData) -> bool:
        """Check if an item has been seen before.

        Args:
            item_id: Unique item identifier
            seen_data: Seen items data

        Returns:
            bool: True if item was seen before
        """
        return item_id in seen_data.items

    def mark_item_seen(
        self,
        item: ContentItem,
        seen_data: SeenItemsData,
        processed: bool = True
    ) -> None:
        """Mark an item as seen.

        Args:
            item: Content item to mark
            seen_data: Seen items data to update
            processed: Whether the item was fully processed
        """
        seen_data.items[item.id] = SeenItem(
            first_seen=datetime.utcnow(),
            processed=processed,
            score=item.ai_score
        )

    def cleanup_old_seen_items(
        self,
        seen_data: SeenItemsData,
        days: int = 30
    ) -> int:
        """Remove seen items older than specified days.

        Args:
            seen_data: Seen items data to clean
            days: Number of days to retain

        Returns:
            int: Number of items removed
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        before_count = len(seen_data.items)

        seen_data.items = {
            item_id: item
            for item_id, item in seen_data.items.items()
            if item.first_seen > cutoff
        }

        return before_count - len(seen_data.items)

    def save_daily_summary(self, date: str, markdown: str) -> Path:
        """Save daily summary to markdown file.

        Args:
            date: Date string (YYYY-MM-DD)
            markdown: Markdown content

        Returns:
            Path: Path to saved file
        """
        filename = f"horizon-{date}.md"
        filepath = self.summaries_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown)

        return filepath
