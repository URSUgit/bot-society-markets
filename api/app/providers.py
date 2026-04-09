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
    PREDICTION_POSITIVE_TERMS = ("approve", "approval", "launch", "buy", "higher", "up", "above", "hit", "surpass", "ath", "rally")
    PREDICTION_NEGATIVE_TERMS = ("sell", "sells", "down", "below", "fall", "lower", "reject", "rejection", "lawsuit", "hack", "ban", "outflow", "liquidation")

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

    @staticmethod
    def _safe_float(value, default: float | None = None) -> float | None:
        if value in (None, "", "null"):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _market_engagement_score(self, *, liquidity: float = 0.0, volume: float = 0.0) -> float:
        activity = max(0.0, liquidity) + max(0.0, volume)
        if activity <= 0:
            return 0.12
        return round(_clamp(math.log1p(activity) / 13, 0.12, 0.98), 6)

    def _prediction_probability(self, *values) -> float | None:
        parsed = [self._safe_float(value) for value in values]
        numeric = [value for value in parsed if value is not None]
        if not numeric:
            return None
        if len(numeric) >= 2:
            return round(_clamp(sum(numeric[:2]) / 2, 0.0, 1.0), 6)
        return round(_clamp(numeric[0], 0.0, 1.0), 6)

    def _prediction_market_sentiment(self, text: str, probability: float, snapshot: dict) -> float:
        positive_hits = sum(text.count(term) for term in self.PREDICTION_POSITIVE_TERMS)
        negative_hits = sum(text.count(term) for term in self.PREDICTION_NEGATIVE_TERMS)
        polarity = -1.0 if negative_hits > positive_hits else 1.0
        probability_component = ((probability - 0.5) * 2.0) * polarity
        market_component = (float(snapshot["signal_bias"]) * 0.2) + (float(snapshot["trend_score"]) * 0.1)
        return round(_clamp(probability_component + market_component, -1.0, 1.0), 6)


PROVIDER_TRUST_BASE = {
    "seed-provider": 0.82,
    "demo-signal-provider": 0.72,
    "rss-news-provider": 0.78,
    "reddit-oauth-provider": 0.74,
    "polymarket-gamma-provider": 0.86,
    "kalshi-public-provider": 0.85,
}

SOURCE_TYPE_TRUST_ADJUSTMENT = {
    "macro": 0.08,
    "news": 0.05,
    "social": 0.0,
    "prediction-market": 0.1,
}


def derive_signal_quality(signal: dict, *, now: datetime | None = None) -> dict[str, float]:
    now = now or datetime.now(timezone.utc)
    observed_at = signal.get("observed_at")
    provider_name = str(signal.get("provider_name") or "seed-provider")
    source_type = str(signal.get("source_type") or signal.get("channel") or "news")
    relevance = float(signal.get("relevance") or 0.55)
    engagement = float(signal.get("engagement_score") or 0.0)

    base_trust = PROVIDER_TRUST_BASE.get(provider_name, 0.68)
    provider_trust_score = _clamp(base_trust + SOURCE_TYPE_TRUST_ADJUSTMENT.get(source_type, 0.0), 0.45, 0.96)

    freshness_score = 0.7
    if observed_at:
        try:
            age_hours = max(0.0, (now - parse_timestamp(str(observed_at))).total_seconds() / 3600)
            freshness_score = _clamp(math.exp(-age_hours / 36), 0.18, 1.0)
        except ValueError:
            freshness_score = 0.55

    engagement_component = _clamp(engagement, 0.0, 1.0)
    source_quality_score = _clamp(
        (provider_trust_score * 0.48) + (freshness_score * 0.24) + (relevance * 0.18) + (engagement_component * 0.10),
        0.0,
        1.0,
    )
    return {
        "provider_trust_score": round(provider_trust_score, 6),
        "freshness_score": round(freshness_score, 6),
        "source_quality_score": round(source_quality_score, 6),
    }


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


class HyperliquidMarketProvider(MarketProviderBase):
    source_name = "hyperliquid-public-provider"
    COIN_SYMBOLS = {
        "bitcoin": "BTC",
        "ethereum": "ETH",
        "solana": "SOL",
    }

    def __init__(self, *, tracked_coin_ids: tuple[str, ...], dex: str = "") -> None:
        self.tracked_coin_ids = tracked_coin_ids
        self.dex = dex

    def generate(self, latest_snapshots: list[dict], cycle_index: int) -> list[dict]:
        body: dict[str, str] = {"type": "allMids"}
        if self.dex:
            body["dex"] = self.dex
        request = Request(
            "https://api.hyperliquid.xyz/info",
            data=json.dumps(body).encode("utf-8"),
            headers={"accept": "application/json", "content-type": "application/json", "user-agent": "BotSocietyMarkets/0.8"},
            method="POST",
        )
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))

        latest_snapshot_map = {snapshot["asset"]: snapshot for snapshot in latest_snapshots}
        observed_at = to_timestamp(datetime.now(timezone.utc))
        generated: list[dict] = []
        for coin_id in self.tracked_coin_ids:
            asset = self.COIN_SYMBOLS.get(coin_id, coin_id.upper())
            raw_price = payload.get(asset)
            if raw_price is None:
                continue
            price = float(raw_price)
            prior = latest_snapshot_map.get(asset)
            prior_price = float(prior["price"]) if prior and prior.get("price") else price
            change_pct = ((price - prior_price) / prior_price) if prior_price else 0.0
            inherited_volume = float(prior["volume_24h"]) if prior and prior.get("volume_24h") else 0.0
            base_volume = inherited_volume if inherited_volume > 0 else price * 100000
            volatility = min(0.25, max(0.02, abs(change_pct) * 1.8 + (float(prior["volatility"]) * 0.45 if prior else 0.02)))
            trend_score = max(-1.0, min(1.0, round(change_pct * 10, 6)))
            prior_bias = float(prior["signal_bias"]) if prior else 0.0
            signal_bias = max(-1.0, min(1.0, round((trend_score * 0.72) + (prior_bias * 0.28), 6)))
            generated.append(
                {
                    "asset": asset,
                    "as_of": observed_at,
                    "price": price,
                    "change_24h": round(change_pct, 6),
                    "volume_24h": round(base_volume * (1 + min(0.08, abs(change_pct))), 2),
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


class PolymarketSignalProvider(AssetAwareSignalProvider):
    source_name = "polymarket-gamma-provider"
    MAX_SIGNALS_PER_ASSET = 2

    def __init__(self, *, tag_id: int, event_limit: int) -> None:
        self.tag_id = tag_id
        self.event_limit = event_limit

    def readiness(self) -> ProviderReadiness:
        if self.tag_id < 1:
            return ProviderReadiness(False, "Polymarket venue mode requires a positive BSM_POLYMARKET_TAG_ID")
        return ProviderReadiness(True)

    def generate(self, market_batch: list[dict], cycle_index: int) -> list[dict]:
        latest_snapshot_map = {snapshot["asset"]: snapshot for snapshot in market_batch}
        batch_id = f"polymarket-cycle-{cycle_index}"
        generated: list[dict] = []
        seen_ids: set[str] = set()
        asset_counts: dict[str, int] = {}

        query = urlencode(
            {
                "tag_id": str(self.tag_id),
                "active": "true",
                "closed": "false",
                "limit": str(self.event_limit),
            }
        )
        request = Request(
            f"https://gamma-api.polymarket.com/events?{query}",
            headers={"accept": "application/json", "user-agent": "BotSocietyMarkets/0.8"},
        )
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        for event in payload:
            title = self._clean_text(str(event.get("title") or "Untitled Polymarket event"))
            description = self._clean_text(str(event.get("description") or title))
            body = f" {title} {description} ".lower()
            asset = self._infer_asset(body, latest_snapshot_map.keys())
            if not asset:
                continue
            if asset_counts.get(asset, 0) >= self.MAX_SIGNALS_PER_ASSET:
                continue
            snapshot = latest_snapshot_map.get(asset)
            if not snapshot:
                continue
            market = self._select_market(event.get("markets") or [])
            if not market:
                continue
            external_id = f"polymarket-{market.get('id')}"
            if external_id in seen_ids:
                continue
            probability = self._prediction_probability(
                market.get("lastTradePrice"),
                self._prediction_probability(market.get("bestBid"), market.get("bestAsk")),
            )
            if probability is None:
                continue
            seen_ids.add(external_id)
            liquidity = self._safe_float(market.get("liquidityNum"), self._safe_float(event.get("liquidityClob"), 0.0)) or 0.0
            volume = self._safe_float(market.get("volume24hrClob"), self._safe_float(event.get("volume24hr"), 0.0)) or 0.0
            engagement_score = self._market_engagement_score(liquidity=liquidity, volume=volume)
            sentiment = self._prediction_market_sentiment(body, probability, snapshot)
            relevance = self._infer_relevance(body, asset, snapshot, engagement_bonus=min(0.18, engagement_score * 0.18))
            market_title = self._clean_text(str(market.get("question") or title))
            generated.append(
                {
                    "external_id": external_id,
                    "asset": asset,
                    "source": "Polymarket",
                    "provider_name": self.source_name,
                    "source_type": "prediction-market",
                    "author_handle": None,
                    "engagement_score": engagement_score,
                    "channel": "venue",
                    "title": market_title[:180],
                    "summary": (
                        f"Polymarket YES probability {probability * 100:.1f}% on '{market_title}'. "
                        f"Liquidity {liquidity:,.0f}, 24h volume {volume:,.0f}."
                    )[:360],
                    "sentiment": sentiment,
                    "relevance": relevance,
                    "url": f"https://polymarket.com/event/{event.get('slug') or market.get('slug') or ''}",
                    "observed_at": market.get("updatedAt") or event.get("updatedAt") or to_timestamp(datetime.now(timezone.utc)),
                    "ingest_batch_id": batch_id,
                }
            )
            asset_counts[asset] = asset_counts.get(asset, 0) + 1

        if not generated:
            raise ValueError("Polymarket did not yield tracked-asset venue signals for the configured universe")
        return generated

    def _select_market(self, markets: list[dict]) -> dict | None:
        active_markets = [
            market
            for market in markets
            if bool(market.get("active")) and not bool(market.get("closed")) and bool(market.get("acceptingOrders", True))
        ]
        if not active_markets:
            return None
        return max(
            active_markets,
            key=lambda market: (
                self._safe_float(market.get("volume24hrClob"), 0.0) or 0.0,
                self._safe_float(market.get("volumeClob"), 0.0) or 0.0,
                self._safe_float(market.get("liquidityClob"), 0.0) or 0.0,
            ),
        )


class KalshiSignalProvider(AssetAwareSignalProvider):
    source_name = "kalshi-public-provider"
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    MAX_SIGNALS_PER_ASSET = 2

    def __init__(self, *, category: str, series_limit: int, markets_per_series: int) -> None:
        self.category = category
        self.series_limit = series_limit
        self.markets_per_series = markets_per_series

    def readiness(self) -> ProviderReadiness:
        if not self.category.strip():
            return ProviderReadiness(False, "Kalshi venue mode requires BSM_KALSHI_CATEGORY")
        return ProviderReadiness(True)

    def generate(self, market_batch: list[dict], cycle_index: int) -> list[dict]:
        latest_snapshot_map = {snapshot["asset"]: snapshot for snapshot in market_batch}
        batch_id = f"kalshi-cycle-{cycle_index}"
        generated: list[dict] = []
        seen_ids: set[str] = set()
        asset_counts: dict[str, int] = {}

        for series in self._fetch_series():
            title = self._clean_text(str(series.get("title") or "Untitled Kalshi series"))
            tags = " ".join(str(tag) for tag in (series.get("tags") or []))
            body = f" {title} {tags} ".lower()
            asset = self._infer_asset(body, latest_snapshot_map.keys())
            if not asset:
                continue
            if asset_counts.get(asset, 0) >= self.MAX_SIGNALS_PER_ASSET:
                continue
            snapshot = latest_snapshot_map.get(asset)
            if not snapshot:
                continue
            try:
                market = self._select_market(self._fetch_markets(str(series.get("ticker") or "")))
            except Exception as exc:
                if generated and "429" in str(exc):
                    break
                raise
            if not market:
                continue
            external_id = f"kalshi-{market.get('ticker')}"
            if external_id in seen_ids:
                continue
            probability = self._prediction_probability(
                market.get("last_price_dollars"),
                self._prediction_probability(market.get("yes_bid_dollars"), market.get("yes_ask_dollars")),
            )
            if probability is None:
                continue
            seen_ids.add(external_id)
            liquidity = self._safe_float(market.get("liquidity_dollars"), 0.0) or 0.0
            volume = self._safe_float(market.get("volume_24h_fp"), self._safe_float(market.get("volume_fp"), 0.0)) or 0.0
            engagement_score = self._market_engagement_score(liquidity=liquidity, volume=volume)
            market_title = self._clean_text(str(market.get("title") or title))
            full_text = f" {title} {market_title} {tags} ".lower()
            sentiment = self._prediction_market_sentiment(full_text, probability, snapshot)
            relevance = self._infer_relevance(full_text, asset, snapshot, engagement_bonus=min(0.18, engagement_score * 0.18))
            generated.append(
                {
                    "external_id": external_id,
                    "asset": asset,
                    "source": "Kalshi",
                    "provider_name": self.source_name,
                    "source_type": "prediction-market",
                    "author_handle": None,
                    "engagement_score": engagement_score,
                    "channel": "venue",
                    "title": market_title[:180],
                    "summary": (
                        f"Kalshi YES probability {probability * 100:.1f}% on '{market_title}'. "
                        f"Series {title}; liquidity {liquidity:,.0f}, volume {volume:,.0f}."
                    )[:360],
                    "sentiment": sentiment,
                    "relevance": relevance,
                    "url": f"https://kalshi.com/markets/{str(series.get('ticker') or '').lower()}",
                    "observed_at": market.get("updated_time") or market.get("created_time") or to_timestamp(datetime.now(timezone.utc)),
                    "ingest_batch_id": batch_id,
                }
            )
            asset_counts[asset] = asset_counts.get(asset, 0) + 1

        if not generated:
            raise ValueError("Kalshi did not yield tracked-asset venue signals for the configured universe")
        return generated

    def _fetch_series(self) -> list[dict]:
        query = urlencode({"category": self.category, "limit": str(self.series_limit)})
        request = Request(
            f"{self.BASE_URL}/series?{query}",
            headers={"accept": "application/json", "user-agent": "BotSocietyMarkets/0.8"},
        )
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("series") or []

    def _fetch_markets(self, series_ticker: str) -> list[dict]:
        if not series_ticker:
            return []
        query = urlencode({"series_ticker": series_ticker, "status": "open", "limit": str(self.markets_per_series)})
        request = Request(
            f"{self.BASE_URL}/markets?{query}",
            headers={"accept": "application/json", "user-agent": "BotSocietyMarkets/0.8"},
        )
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("markets") or []

    def _select_market(self, markets: list[dict]) -> dict | None:
        active_markets = [market for market in markets if str(market.get("status") or "").lower() == "active"]
        if not active_markets:
            return None
        return max(
            active_markets,
            key=lambda market: (
                self._safe_float(market.get("volume_24h_fp"), 0.0) or 0.0,
                self._safe_float(market.get("volume_fp"), 0.0) or 0.0,
                self._safe_float(market.get("liquidity_dollars"), 0.0) or 0.0,
            ),
        )



def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
