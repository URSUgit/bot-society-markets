from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .utils import parse_timestamp, to_timestamp

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(slots=True)
class ProviderReadiness:
    ready: bool
    warning: str | None = None


class MarketProviderBase:
    source_name = "market-provider"

    def readiness(self) -> ProviderReadiness:
        return ProviderReadiness(ready=True)


class SignalProviderBase:
    source_name = "signal-provider"

    def readiness(self) -> ProviderReadiness:
        return ProviderReadiness(ready=True)


class AssetAwareSignalProvider(SignalProviderBase):
    ASSET_ALIASES = {
        "BTC": ("bitcoin", "btc", "xbt", "blackrock etf", "spot btc"),
        "ETH": ("ethereum", "eth", "ether", "staking", "l2"),
        "SOL": ("solana", "sol", "jupiter", "memecoin", "validator"),
    }
    POSITIVE_TERMS = ("surge", "gain", "rally", "approval", "breakout", "strong", "higher", "bull", "inflow", "growth")
    NEGATIVE_TERMS = ("drop", "fall", "risk", "hack", "bear", "outflow", "lower", "lawsuit", "pressure", "liquidation")

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    def _clean_text(self, value: str) -> str:
        text = unescape(value)
        text = TAG_RE.sub(" ", text)
        return WHITESPACE_RE.sub(" ", text).strip()

    def _infer_asset(self, text: str, tracked_assets) -> str | None:
        scores: list[tuple[int, str]] = []
        for asset, aliases in self.ASSET_ALIASES.items():
            if asset not in tracked_assets:
                continue
            score = 0
            for alias in aliases:
                if " " in alias:
                    score += 1 if alias in text else 0
                else:
                    score += 1 if re.search(rf"\b{re.escape(alias)}\b", text) else 0
            if score:
                scores.append((score, asset))
        if not scores:
            return None
        scores.sort(reverse=True)
        return scores[0][1]

    def _infer_sentiment(self, text: str, snapshot: dict, *, boost: float = 1.0) -> float:
        positive_hits = sum(text.count(term) for term in self.POSITIVE_TERMS)
        negative_hits = sum(text.count(term) for term in self.NEGATIVE_TERMS)
        lexical = (positive_hits - negative_hits) * 0.12 * boost
        market_component = (float(snapshot["signal_bias"]) * 0.45) + (float(snapshot["trend_score"]) * 0.2)
        return round(_clamp(lexical + market_component, -1.0, 1.0), 6)

    def _infer_relevance(self, text: str, asset: str, snapshot: dict, *, engagement_bonus: float = 0.0) -> float:
        alias_hits = 0
        for alias in self.ASSET_ALIASES.get(asset, ()):
            if " " in alias:
                alias_hits += 1 if alias in text else 0
            else:
                alias_hits += 1 if re.search(rf"\b{re.escape(alias)}\b", text) else 0
        narrative_strength = min(0.18, 0.04 * alias_hits)
        market_strength = min(0.16, abs(float(snapshot["trend_score"])) * 0.2)
        return round(_clamp(0.58 + narrative_strength + market_strength + engagement_bonus, 0.45, 0.96), 6)


class DemoMarketProvider(MarketProviderBase):
    source_name = "demo-market-provider"

    def generate(self, latest_snapshots: list[dict], cycle_index: int) -> list[dict]:
        if not latest_snapshots:
            return []

        latest_time = max(parse_timestamp(snapshot["as_of"]) for snapshot in latest_snapshots)
        next_time = latest_time + timedelta(hours=6)
        adjustments = {
            "BTC": (0.006 + 0.001 * (cycle_index % 3), 0.03, 0.02),
            "ETH": (0.009 + 0.001 * (cycle_index % 2), 0.04, 0.025),
            "SOL": (0.013 + 0.002 * (cycle_index % 2), 0.06, 0.04),
        }

        generated = []
        for snapshot in latest_snapshots:
            base_move, volatility_bump, bias_bump = adjustments.get(snapshot["asset"], (0.005, 0.02, 0.02))
            generated.append(
                {
                    "asset": snapshot["asset"],
                    "as_of": to_timestamp(next_time),
                    "price": round(snapshot["price"] * (1 + base_move), 2),
                    "change_24h": round(base_move, 6),
                    "volume_24h": round(snapshot["volume_24h"] * (1 + 0.02 + 0.01 * cycle_index), 2),
                    "volatility": round(snapshot["volatility"] + volatility_bump * 0.05, 6),
                    "trend_score": max(-1.0, min(1.0, round(snapshot["trend_score"] + 0.06, 6))),
                    "signal_bias": max(-1.0, min(1.0, round(snapshot["signal_bias"] + bias_bump, 6))),
                    "source": self.source_name,
                }
            )
        return generated


class CoinGeckoMarketProvider(MarketProviderBase):
    source_name = "coingecko"
    SYMBOL_MAP = {
        "bitcoin": "BTC",
        "ethereum": "ETH",
        "solana": "SOL",
    }

    def __init__(self, *, plan: str, api_key: str | None, tracked_coin_ids: tuple[str, ...]) -> None:
        self.plan = plan
        self.api_key = api_key
        self.tracked_coin_ids = tracked_coin_ids
        self.base_url = "https://pro-api.coingecko.com/api/v3" if plan == "pro" else "https://api.coingecko.com/api/v3"

    def readiness(self) -> ProviderReadiness:
        if self.plan == "pro" and not self.api_key:
            return ProviderReadiness(False, "CoinGecko Pro mode requires BSM_COINGECKO_API_KEY")
        return ProviderReadiness(True)

    def generate(self, latest_snapshots: list[dict], cycle_index: int) -> list[dict]:
        query = urlencode(
            {
                "vs_currency": "usd",
                "ids": ",".join(self.tracked_coin_ids),
                "price_change_percentage": "24h",
                "precision": "full",
            }
        )
        headers = {"accept": "application/json"}
        if self.api_key:
            header_name = "x-cg-pro-api-key" if self.plan == "pro" else "x-cg-demo-api-key"
            headers[header_name] = self.api_key

        request = Request(f"{self.base_url}/coins/markets?{query}", headers=headers)
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))

        generated: list[dict] = []
        latest_snapshot_map = {snapshot["asset"]: snapshot for snapshot in latest_snapshots}
        for coin in payload:
            asset = self.SYMBOL_MAP.get(coin.get("id"), coin.get("symbol", "").upper())
            if not asset:
                continue
            change_pct = float(coin.get("price_change_percentage_24h") or 0.0) / 100
            prior = latest_snapshot_map.get(asset)
            volatility = min(0.25, max(0.02, abs(change_pct) * 1.6 + 0.02))
            trend_score = max(-1.0, min(1.0, round(change_pct * 8, 6)))
            prior_bias = float(prior["signal_bias"]) if prior else 0.0
            signal_bias = max(-1.0, min(1.0, round((trend_score * 0.7) + (prior_bias * 0.3), 6)))
            last_updated = coin.get("last_updated") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            generated.append(
                {
                    "asset": asset,
                    "as_of": last_updated.replace(".000", ""),
                    "price": float(coin.get("current_price") or 0.0),
                    "change_24h": round(change_pct, 6),
                    "volume_24h": float(coin.get("total_volume") or 0.0),
                    "volatility": round(volatility, 6),
                    "trend_score": trend_score,
                    "signal_bias": signal_bias,
                    "source": self.source_name,
                }
            )
        return generated


class DemoSignalProvider(AssetAwareSignalProvider):
    source_name = "demo-signal-provider"

    def generate(self, market_batch: list[dict], cycle_index: int) -> list[dict]:
        generated = []
        for snapshot in market_batch:
            observed_at = snapshot["as_of"]
            asset = snapshot["asset"]
            positive = snapshot["signal_bias"] >= 0
            social_sentiment = round(snapshot["signal_bias"] * 0.92, 6)
            news_sentiment = round(snapshot["trend_score"] * 0.78, 6)

            generated.append(
                {
                    "external_id": f"demo-social-{cycle_index}-{asset.lower()}",
                    "asset": asset,
                    "source": "X",
                    "provider_name": self.source_name,
                    "source_type": "social",
                    "author_handle": "@demoflowdesk",
                    "engagement_score": 0.74 if asset != "SOL" else 0.82,
                    "channel": "social",
                    "title": f"{asset} trader cluster {'leans' if positive else 'turns'} {'higher' if positive else 'defensive'} on the next session",
                    "summary": f"A curated watchlist of market accounts shows {'expanding' if positive else 'softening'} conviction around {asset}, with narrative strength tied to price structure.",
                    "sentiment": social_sentiment,
                    "relevance": 0.8 if asset != "SOL" else 0.86,
                    "url": f"https://example.com/live/social/{cycle_index}/{asset.lower()}",
                    "observed_at": observed_at,
                    "ingest_batch_id": f"demo-cycle-{cycle_index}",
                }
            )
            generated.append(
                {
                    "external_id": f"demo-news-{cycle_index}-{asset.lower()}",
                    "asset": asset,
                    "source": "DeskWire",
                    "provider_name": self.source_name,
                    "source_type": "news",
                    "author_handle": "deskwire-research",
                    "engagement_score": None,
                    "channel": "news",
                    "title": f"{asset} market structure {'improves' if positive else 'faces a balance check'} as flows reset",
                    "summary": f"Desk commentary frames {asset} as {'constructive' if positive else 'fragile'} after the most recent market repricing phase.",
                    "sentiment": news_sentiment,
                    "relevance": 0.76,
                    "url": f"https://example.com/live/news/{cycle_index}/{asset.lower()}",
                    "observed_at": observed_at,
                    "ingest_batch_id": f"demo-cycle-{cycle_index}",
                }
            )
        return generated


class RSSNewsSignalProvider(AssetAwareSignalProvider):
    source_name = "rss-news-provider"

    def __init__(self, *, feed_urls: tuple[str, ...]) -> None:
        self.feed_urls = feed_urls

    def readiness(self) -> ProviderReadiness:
        if not self.feed_urls:
            return ProviderReadiness(False, "RSS mode requires BSM_RSS_FEED_URLS")
        return ProviderReadiness(True)

    def generate(self, market_batch: list[dict], cycle_index: int) -> list[dict]:
        if not self.feed_urls:
            raise ValueError("RSS signal provider requires at least one feed URL")

        latest_snapshot_map = {snapshot["asset"]: snapshot for snapshot in market_batch}
        batch_id = f"rss-cycle-{cycle_index}"
        generated: list[dict] = []
        seen_ids: set[str] = set()

        for feed_url in self.feed_urls:
            for entry in self._fetch_entries(feed_url):
                body = f" {entry['title']} {entry['summary']} ".lower()
                asset = self._infer_asset(body, latest_snapshot_map.keys())
                if not asset:
                    continue
                snapshot = latest_snapshot_map.get(asset)
                if not snapshot:
                    continue
                external_id = self._build_external_id(feed_url, entry)
                if external_id in seen_ids:
                    continue
                seen_ids.add(external_id)
                sentiment = self._infer_sentiment(body, snapshot)
                relevance = self._infer_relevance(body, asset, snapshot)
                generated.append(
                    {
                        "external_id": external_id,
                        "asset": asset,
                        "source": self._source_name(feed_url),
                        "provider_name": self.source_name,
                        "source_type": "news",
                        "author_handle": None,
                        "engagement_score": None,
                        "channel": "news",
                        "title": entry["title"][:180],
                        "summary": entry["summary"][:360],
                        "sentiment": sentiment,
                        "relevance": relevance,
                        "url": entry["link"],
                        "observed_at": entry["observed_at"],
                        "ingest_batch_id": batch_id,
                    }
                )

        if not generated:
            raise ValueError("RSS feeds did not yield tracked-asset signals for the configured universe")
        return generated

    def _fetch_entries(self, feed_url: str) -> list[dict[str, str]]:
        request = Request(feed_url, headers={"user-agent": "BotSocietyMarkets/0.7"})
        with urlopen(request, timeout=20) as response:
            payload = response.read()
        root = ElementTree.fromstring(payload)
        entries: list[dict[str, str]] = []

        channel = self._find_child(root, "channel")
        if channel is not None:
            for item in self._find_children(channel, "item"):
                title = self._text(item, "title") or "Untitled feed item"
                summary = self._clean_text(self._text(item, "description", "summary", "encoded") or title)
                link = self._link(item) or feed_url
                observed_at = self._parse_feed_timestamp(self._text(item, "pubDate", "published", "updated"))
                entries.append({"title": self._clean_text(title), "summary": summary, "link": link, "observed_at": observed_at})
            return entries

        for entry in self._find_children(root, "entry"):
            title = self._text(entry, "title") or "Untitled feed item"
            summary = self._clean_text(self._text(entry, "summary", "content") or title)
            link = self._link(entry) or feed_url
            observed_at = self._parse_feed_timestamp(self._text(entry, "updated", "published"))
            entries.append({"title": self._clean_text(title), "summary": summary, "link": link, "observed_at": observed_at})
        return entries

    def _find_child(self, node: ElementTree.Element, name: str) -> ElementTree.Element | None:
        for child in list(node):
            if self._local_name(child.tag) == name:
                return child
        return None

    def _find_children(self, node: ElementTree.Element, name: str) -> list[ElementTree.Element]:
        return [child for child in node.iter() if self._local_name(child.tag) == name]

    def _text(self, node: ElementTree.Element, *names: str) -> str | None:
        for child in list(node):
            if self._local_name(child.tag) in names:
                text = "".join(child.itertext()).strip()
                if text:
                    return text
        return None

    def _link(self, node: ElementTree.Element) -> str | None:
        for child in list(node):
            local_name = self._local_name(child.tag)
            if local_name == "link":
                href = child.attrib.get("href")
                if href:
                    return href.strip()
                text = "".join(child.itertext()).strip()
                if text:
                    return text
        return None

    def _build_external_id(self, feed_url: str, entry: dict[str, str]) -> str:
        digest = hashlib.sha1(f"{feed_url}|{entry['title']}|{entry['observed_at']}".encode("utf-8")).hexdigest()
        return f"rss-{digest[:20]}"

    @staticmethod
    def _source_name(feed_url: str) -> str:
        host = urlparse(feed_url).netloc.lower().removeprefix("www.")
        return host or "rss"

    @staticmethod
    def _parse_feed_timestamp(value: str | None) -> str:
        if not value:
            return to_timestamp(datetime.now(timezone.utc))
        try:
            return to_timestamp(parse_timestamp(value))
        except ValueError:
            try:
                return to_timestamp(parsedate_to_datetime(value))
            except (TypeError, ValueError, IndexError):
                return to_timestamp(datetime.now(timezone.utc))


class RedditSignalProvider(AssetAwareSignalProvider):
    source_name = "reddit-oauth-provider"
    TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
    API_URL = "https://oauth.reddit.com"

    def __init__(
        self,
        *,
        client_id: str | None,
        client_secret: str | None,
        user_agent: str,
        subreddits: tuple[str, ...],
        post_limit: int,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.subreddits = subreddits
        self.post_limit = post_limit

    def readiness(self) -> ProviderReadiness:
        if not self.client_id or not self.client_secret:
            return ProviderReadiness(False, "Reddit mode requires BSM_REDDIT_CLIENT_ID and BSM_REDDIT_CLIENT_SECRET")
        if not self.subreddits:
            return ProviderReadiness(False, "Reddit mode requires at least one subreddit in BSM_REDDIT_SUBREDDITS")
        return ProviderReadiness(True)

    def generate(self, market_batch: list[dict], cycle_index: int) -> list[dict]:
        if not self.client_id or not self.client_secret:
            raise ValueError("Reddit signal provider requires client credentials")
        if not self.subreddits:
            raise ValueError("Reddit signal provider requires subreddit configuration")

        token = self._get_access_token()
        latest_snapshot_map = {snapshot["asset"]: snapshot for snapshot in market_batch}
        batch_id = f"reddit-cycle-{cycle_index}"
        generated: list[dict] = []
        seen_ids: set[str] = set()

        for subreddit in self.subreddits:
            posts = self._fetch_posts(token, subreddit)
            for post in posts:
                title = self._clean_text(str(post.get("title") or "Untitled Reddit post"))
                summary = self._clean_text(str(post.get("selftext") or title))
                body = f" {title} {summary} ".lower()
                asset = self._infer_asset(body, latest_snapshot_map.keys())
                if not asset:
                    continue
                snapshot = latest_snapshot_map.get(asset)
                if not snapshot:
                    continue
                external_id = f"reddit-{post.get('id')}"
                if external_id in seen_ids:
                    continue
                seen_ids.add(external_id)
                score = max(0, int(post.get("score") or 0))
                comments = max(0, int(post.get("num_comments") or 0))
                engagement_score = round(_clamp(math.log1p(score + (comments * 3)) / 8, 0.0, 1.0), 6)
                generated.append(
                    {
                        "external_id": external_id,
                        "asset": asset,
                        "source": f"r/{subreddit}",
                        "provider_name": self.source_name,
                        "source_type": "social",
                        "author_handle": f"u/{post.get('author') or 'unknown'}",
                        "engagement_score": engagement_score,
                        "channel": "social",
                        "title": title[:180],
                        "summary": summary[:360],
                        "sentiment": self._infer_sentiment(body, snapshot, boost=1.1),
                        "relevance": self._infer_relevance(body, asset, snapshot, engagement_bonus=min(0.14, engagement_score * 0.18)),
                        "url": f"https://reddit.com{post.get('permalink') or ''}",
                        "observed_at": to_timestamp(datetime.fromtimestamp(float(post.get('created_utc') or 0), tz=timezone.utc)),
                        "ingest_batch_id": batch_id,
                    }
                )

        if not generated:
            raise ValueError("Reddit feeds did not yield tracked-asset signals for the configured universe")
        return generated

    def _get_access_token(self) -> str:
        credentials = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        headers = {
            "authorization": f"Basic {base64.b64encode(credentials).decode('ascii')}",
            "user-agent": self.user_agent,
            "content-type": "application/x-www-form-urlencoded",
        }
        request = Request(
            self.TOKEN_URL,
            data=urlencode({"grant_type": "client_credentials"}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        token = payload.get("access_token")
        if not token:
            raise ValueError("Reddit access token was not returned")
        return str(token)

    def _fetch_posts(self, token: str, subreddit: str) -> list[dict]:
        query = urlencode({"limit": str(self.post_limit), "raw_json": "1"})
        headers = {
            "authorization": f"Bearer {token}",
            "user-agent": self.user_agent,
            "accept": "application/json",
        }
        request = Request(f"{self.API_URL}/r/{subreddit}/hot?{query}", headers=headers)
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        children = payload.get("data", {}).get("children", [])
        return [child.get("data", {}) for child in children if child.get("kind") == "t3"]



def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
