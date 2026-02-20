"""Twitter scraper via syndication API and RSS bridges."""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
from email.utils import parsedate_to_datetime
import httpx
import feedparser

from .base import BaseScraper
from ..models import ContentItem, SourceType, TwitterSourceConfig

logger = logging.getLogger(__name__)

# Max tweets to enrich with FxTwitter (to avoid too many requests)
FXTWITTER_ENRICH_LIMIT = 10

class TwitterScraper(BaseScraper):
    """Scraper for Twitter/X content.

    Supports three modes (tried in order):
    1. Syndication API: Twitter's public embed endpoint (recommended, no auth needed)
    2. Direct RSS URL: User-provided RSS bridge (RSSHub, Nitter, etc.)
    3. Nitter discovery: Tries nitter_instances in order (unreliable since 2024)

    After fetching, enriches tweets with FxTwitter API for fuller engagement data.
    """

    SYNDICATION_URL = "https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
    FXTWITTER_URL = "https://api.fxtwitter.com/{username}/status/{tweet_id}"

    def __init__(self, sources: List[TwitterSourceConfig], http_client: httpx.AsyncClient):
        super().__init__({"sources": sources}, http_client)

    async def fetch(self, since: datetime) -> List[ContentItem]:
        items = []
        for source in self.config["sources"]:
            if not source.enabled:
                continue
            user_items = await self._fetch_user(source, since)
            items.extend(user_items)

        # Enrich top tweets with FxTwitter for richer engagement data
        if items:
            await self._enrich_with_fxtwitter(items)

        return items

    async def _fetch_user(
        self,
        source: TwitterSourceConfig,
        since: datetime
    ) -> List[ContentItem]:
        """Fetch tweets for a user, trying all available methods."""

        # Mode 1: Syndication API (preferred - no auth, structured data)
        items = await self._fetch_via_syndication(source.username, since)
        if items is not None:
            return items

        # Mode 2: Direct RSS URL
        if source.rss_url:
            items = await self._fetch_via_rss(source.rss_url, source.username, since, "custom RSS")
            if items is not None:
                return items

        # Mode 3: Nitter instance discovery (fallback)
        for instance_url in source.nitter_instances:
            rss_url = f"{instance_url.rstrip('/')}/{source.username}/rss"
            items = await self._fetch_via_rss(rss_url, source.username, since, instance_url)
            if items is not None:
                return items

        logger.info("Twitter @%s: no working source found", source.username)
        return []

    # ── Syndication API ──────────────────────────────────────────────

    async def _fetch_via_syndication(
        self,
        username: str,
        since: datetime
    ) -> Optional[List[ContentItem]]:
        """Fetch tweets via Twitter's syndication (embed) API.

        This endpoint is public and returns up to 100 tweets as JSON
        embedded in an HTML page. No authentication required.
        """
        url = self.SYNDICATION_URL.format(username=username)

        try:
            response = await self.client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko)"
                },
                follow_redirects=True,
                timeout=15.0
            )

            if response.status_code != 200:
                logger.debug("Twitter @%s: syndication API returned %d", username, response.status_code)
                return None

            # Extract __NEXT_DATA__ JSON from HTML
            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                response.text
            )

            if not match:
                logger.debug("Twitter @%s: syndication API returned unexpected format", username)
                return None

            data = json.loads(match.group(1))
            timeline = data.get("props", {}).get("pageProps", {}).get("timeline", {})
            entries = timeline.get("entries", [])

            if not entries:
                print(f"   Twitter @{username}: syndication API returned no tweets")
                return None

            # Parse tweets
            items = []
            for entry in entries:
                if entry.get("type") != "tweet":
                    continue

                content = entry.get("content", {})
                tweet = content.get("tweet", content)

                # Parse date
                created_at_str = tweet.get("created_at", "")
                if not created_at_str:
                    continue

                try:
                    published_at = parsedate_to_datetime(created_at_str)
                    if published_at.tzinfo is None:
                        published_at = published_at.replace(tzinfo=timezone.utc)
                except Exception:
                    continue

                if published_at < since:
                    continue

                # Extract tweet data
                tweet_id = entry.get("entry_id", "").replace("tweet-", "")
                full_text = tweet.get("full_text", tweet.get("text", ""))
                screen_name = tweet.get("user", {}).get("screen_name", username)

                display_title = full_text[:117] + "..." if len(full_text) > 120 else full_text
                # Remove newlines from title
                display_title = display_title.replace("\n", " ")

                tweet_url = f"https://x.com/{screen_name}/status/{tweet_id}"

                items.append(ContentItem(
                    id=self._generate_id("twitter", username, tweet_id),
                    source_type=SourceType.TWITTER,
                    title=f"@{screen_name}: {display_title}",
                    url=tweet_url,
                    content=full_text,
                    author=screen_name,
                    published_at=published_at,
                    metadata={
                        "platform": "twitter",
                        "username": screen_name,
                        "favorite_count": tweet.get("favorite_count", 0),
                        "retweet_count": tweet.get("retweet_count", 0),
                        "reply_count": tweet.get("reply_count", 0),
                    }
                ))

            print(f"   Twitter @{username}: fetched {len(items)} tweets via syndication API")
            return items

        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
            print(f"   Twitter @{username}: syndication API failed ({e})")
            return None

    # ── FxTwitter Enrichment ─────────────────────────────────────────

    async def _enrich_with_fxtwitter(self, items: List[ContentItem]) -> None:
        """Enrich tweets with FxTwitter API for views, bookmarks, and reply counts.

        FxTwitter is a free, no-auth API that provides richer engagement data
        than the syndication API.
        """
        # Sort by engagement, enrich most popular first
        sorted_items = sorted(
            items,
            key=lambda x: x.metadata.get("favorite_count", 0),
            reverse=True
        )
        to_enrich = sorted_items[:FXTWITTER_ENRICH_LIMIT]

        tasks = [self._fetch_fxtwitter(item) for item in to_enrich]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_fxtwitter(self, item: ContentItem) -> None:
        """Fetch enriched data for a single tweet from FxTwitter."""
        username = item.metadata.get("username", item.author or "")
        tweet_id = str(item.url).split("/")[-1]

        url = self.FXTWITTER_URL.format(username=username, tweet_id=tweet_id)
        try:
            response = await self.client.get(url, timeout=10.0)
            if response.status_code != 200:
                return

            data = response.json()
            tweet = data.get("tweet")
            if not tweet:
                return

            # Update metadata with richer engagement data
            item.metadata["views"] = tweet.get("views", 0)
            item.metadata["bookmarks"] = tweet.get("bookmarks", 0)
            item.metadata["reply_count"] = tweet.get("replies", item.metadata.get("reply_count", 0))

            # FxTwitter may have more accurate counts
            if tweet.get("likes", 0) > item.metadata.get("favorite_count", 0):
                item.metadata["favorite_count"] = tweet["likes"]
            if tweet.get("retweets", 0) > item.metadata.get("retweet_count", 0):
                item.metadata["retweet_count"] = tweet["retweets"]

            # Community note if present
            if tweet.get("community_note"):
                item.metadata["community_note"] = tweet["community_note"]

        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            pass  # Best-effort enrichment

    # ── RSS Fallback ─────────────────────────────────────────────────

    async def _fetch_via_rss(
        self,
        url: str,
        username: str,
        since: datetime,
        label: str
    ) -> Optional[List[ContentItem]]:
        """Try fetching from an RSS URL (Nitter, RSSHub, etc.)."""
        try:
            response = await self.client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko)"
                },
                follow_redirects=True,
                timeout=15.0
            )

            if response.status_code != 200:
                return None

            text = response.text.strip()
            if not text:
                return None

            # Detect known failure patterns
            if "not yet whitelisted" in text.lower():
                return None
            if "<title>Verifying your browser" in text or "challenge-platform" in text:
                return None
            if text.startswith("<!") or text.startswith("<html"):
                return None

            feed = feedparser.parse(text)
            if not feed.entries:
                return None

            items = []
            for entry in feed.entries:
                published_at = self._parse_rss_date(entry)
                if not published_at or published_at < since:
                    continue

                title = entry.get("title", "")
                link = entry.get("link", f"https://x.com/{username}")
                content = entry.get("summary", entry.get("description", ""))
                entry_id = entry.get("id", entry.get("link", ""))
                tweet_id = entry_id.split("/")[-1].split("#")[0] if "/" in entry_id else str(hash(entry_id))

                display_title = title[:117] + "..." if len(title) > 120 else title

                items.append(ContentItem(
                    id=self._generate_id("twitter", username, tweet_id),
                    source_type=SourceType.TWITTER,
                    title=f"@{username}: {display_title}",
                    url=link,
                    content=content,
                    author=username,
                    published_at=published_at,
                    metadata={"platform": "twitter", "username": username}
                ))

            if items:
                print(f"   Twitter @{username}: fetched {len(items)} tweets via {label}")
            return items if items else None

        except httpx.HTTPError:
            return None

    def _parse_rss_date(self, entry: dict) -> Optional[datetime]:
        """Parse publication date from RSS entry."""
        for field in ["published", "updated", "created"]:
            if f"{field}_parsed" in entry and entry[f"{field}_parsed"]:
                import calendar
                try:
                    ts = calendar.timegm(entry[f"{field}_parsed"])
                    return datetime.fromtimestamp(ts, tz=timezone.utc)
                except Exception:
                    continue
            if field in entry:
                try:
                    dt = parsedate_to_datetime(entry[field])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except Exception:
                    continue
        return None
