from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Direction, SocialPlatform


ASSET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "BTC": ("btc", "bitcoin"),
    "ETH": ("eth", "ethereum"),
    "SOL": ("sol", "solana"),
    "HYPE": ("hyperliquid", "hype"),
    "POLYMARKET": ("polymarket", "prediction market", "prediction-market"),
    "KALSHI": ("kalshi", "event contract", "event market"),
    "SPX": ("s&p", "spx", "spy", "stocks"),
}

BULLISH_TERMS = (
    "bullish",
    "long",
    "buy",
    "breakout",
    "accumulate",
    "upside",
    "rally",
    "higher",
    "risk-on",
)
BEARISH_TERMS = (
    "bearish",
    "short",
    "sell",
    "breakdown",
    "downside",
    "crash",
    "lower",
    "risk-off",
)


@dataclass(slots=True)
class SocialEvidenceRecord:
    external_id: str
    platform: SocialPlatform
    title: str
    summary: str
    url: str
    asset: str
    direction: Direction
    confidence: float
    engagement_score: float
    observed_at: str
    derived_return: float


@dataclass(slots=True)
class DiscoveredSocialTrader:
    slug: str
    display_name: str
    handle: str
    platform: SocialPlatform
    source_url: str
    avatar_seed: str
    avatar_url: str | None
    description: str
    primary_assets: list[str]
    style_tags: list[str]
    signal_count: int
    tracked_years: float
    win_rate: float
    average_roi: float
    roi_if_followed: float
    max_drawdown: float
    sharpe_like: float
    consistency_score: float
    influence_score: float
    recency_score: float
    composite_score: float
    last_signal_at: str | None
    evidence: list[SocialEvidenceRecord] = field(default_factory=list)


@dataclass(slots=True)
class SocialDiscoveryResult:
    provider: str
    youtube_configured: bool
    traders: list[DiscoveredSocialTrader]
    warnings: list[str] = field(default_factory=list)


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "social-trader"


def clamp_value(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def extract_asset(text: str) -> str:
    lowered = text.lower()
    for asset, keywords in ASSET_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return asset
    return "BTC"


def infer_direction(text: str) -> Direction:
    lowered = text.lower()
    bullish = sum(1 for term in BULLISH_TERMS if term in lowered)
    bearish = sum(1 for term in BEARISH_TERMS if term in lowered)
    if bullish > bearish:
        return "bullish"
    if bearish > bullish:
        return "bearish"
    return "neutral"


def confidence_from_text(text: str, engagement_score: float) -> float:
    lowered = text.lower()
    conviction_terms = ("target", "thesis", "because", "probability", "odds", "expected value", "setup", "invalidated")
    conviction = sum(1 for term in conviction_terms if term in lowered) * 0.045
    direction_bonus = 0.06 if infer_direction(text) != "neutral" else 0.0
    return round(clamp_value(0.48 + conviction + direction_bonus + engagement_score * 0.24, 0.35, 0.94), 3)


def deterministic_return(seed: str, direction: Direction) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    raw = int(digest[:8], 16) / 0xFFFFFFFF
    centered = (raw - 0.46) * 0.42
    if direction == "bearish":
        centered *= -0.82
    if direction == "neutral":
        centered *= 0.25
    return round(clamp_value(centered, -0.34, 0.58), 4)


def score_from_events(
    *,
    display_name: str,
    handle: str,
    platform: SocialPlatform,
    source_url: str,
    description: str,
    style_tags: list[str],
    events: list[SocialEvidenceRecord],
) -> DiscoveredSocialTrader:
    now = datetime.now(timezone.utc)
    assets = sorted({event.asset for event in events}) or ["BTC"]
    derived_returns = [event.derived_return for event in events]
    wins = [result for result in derived_returns if result > 0]
    signal_count = len(events)
    win_rate = len(wins) / signal_count if signal_count else 0.0
    average_roi = sum(derived_returns) / signal_count if signal_count else 0.0
    roi_if_followed = math.prod(1 + value for value in derived_returns) - 1 if derived_returns else 0.0
    downside = [value for value in derived_returns if value < 0]
    max_drawdown = min(downside) if downside else -0.01
    variance = sum((value - average_roi) ** 2 for value in derived_returns) / max(1, signal_count)
    sharpe_like = average_roi / math.sqrt(variance) if variance > 0 else average_roi * 5
    consistency_score = clamp_value((win_rate * 0.7) + (1 - abs(max_drawdown)) * 0.3, 0.0, 1.0)
    influence_score = clamp_value(sum(event.engagement_score for event in events) / max(1, signal_count), 0.0, 1.0)
    latest_at = max((event.observed_at for event in events), default=None)
    latest_dt = parse_iso_timestamp(latest_at) if latest_at else now - timedelta(days=180)
    recency_score = clamp_value(1 - ((now - latest_dt).days / 180), 0.1, 1.0)
    composite_score = round(
        clamp_value(
            100
            * (
                win_rate * 0.3
                + clamp_value((roi_if_followed + 0.25) / 1.4, 0.0, 1.0) * 0.3
                + consistency_score * 0.18
                + influence_score * 0.12
                + recency_score * 0.1
            ),
            0,
            100,
        ),
        2,
    )
    first_at = min((parse_iso_timestamp(event.observed_at) for event in events), default=now)
    tracked_years = max(0.1, round((now - first_at).days / 365, 2))
    slug = slugify(f"{platform}-{handle or display_name}")
    return DiscoveredSocialTrader(
        slug=slug,
        display_name=display_name,
        handle=handle,
        platform=platform,
        source_url=source_url,
        avatar_seed=hashlib.sha1(slug.encode("utf-8")).hexdigest()[:12],
        avatar_url=None,
        description=description,
        primary_assets=assets[:5],
        style_tags=style_tags[:6],
        signal_count=signal_count,
        tracked_years=tracked_years,
        win_rate=round(win_rate, 3),
        average_roi=round(average_roi, 4),
        roi_if_followed=round(roi_if_followed, 4),
        max_drawdown=round(max_drawdown, 4),
        sharpe_like=round(sharpe_like, 3),
        consistency_score=round(consistency_score, 3),
        influence_score=round(influence_score, 3),
        recency_score=round(recency_score, 3),
        composite_score=composite_score,
        last_signal_at=latest_at,
        evidence=events[:8],
    )


def parse_iso_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.now(timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class DemoSocialDiscoveryProvider:
    source_name = "demo-social-discovery"

    def discover(self) -> SocialDiscoveryResult:
        now = datetime.now(timezone.utc)
        profiles = [
            (
                "CycleCraft Crypto",
                "@CycleCraft",
                "https://youtube.com/@CycleCraftCrypto",
                "Long-cycle crypto analyst who maps Bitcoin, Ethereum, and liquidity regimes into staged entries.",
                ["cycle model", "liquidity", "BTC", "ETH"],
                ["BTC", "ETH", "SOL"],
            ),
            (
                "Prediction Desk",
                "@PredictionDesk",
                "https://youtube.com/@PredictionDesk",
                "Prediction-market operator focused on Polymarket odds, news catalysts, and probability dislocations.",
                ["prediction markets", "Polymarket", "event risk"],
                ["POLYMARKET", "BTC", "KALSHI"],
            ),
            (
                "Macro Tape Studio",
                "@MacroTape",
                "https://youtube.com/@MacroTapeStudio",
                "Macro trader translating rates, dollar liquidity, and volatility into crypto risk-on or risk-off regimes.",
                ["macro", "rates", "risk regime"],
                ["BTC", "ETH", "SPX"],
            ),
            (
                "Onchain Athena",
                "@OnchainAthena",
                "https://youtube.com/@OnchainAthena",
                "On-chain wallet-flow researcher watching whales, perp positioning, and cross-venue liquidity.",
                ["wallet flows", "perps", "liquidity"],
                ["SOL", "HYPE", "ETH"],
            ),
        ]
        traders: list[DiscoveredSocialTrader] = []
        for index, (name, handle, source_url, description, tags, assets) in enumerate(profiles):
            events: list[SocialEvidenceRecord] = []
            for offset in range(8):
                asset = assets[(offset + index) % len(assets)]
                direction: Direction = "bullish" if (offset + index) % 3 != 1 else "bearish"
                observed_at = (now - timedelta(days=offset * 38 + index * 9)).isoformat().replace("+00:00", "Z")
                title = f"{asset} {direction} thesis with invalidation map"
                seed = f"{handle}:{asset}:{direction}:{offset}"
                engagement = round(clamp_value(0.48 + ((offset + 1) / 16) + index * 0.035, 0.1, 0.95), 3)
                events.append(
                    SocialEvidenceRecord(
                        external_id=f"demo-{slugify(handle)}-{asset.lower()}-{offset}",
                        platform="youtube",
                        title=title,
                        summary=(
                            f"{name} framed a {direction} {asset} setup, described the catalyst, "
                            "and published an invalidation level before the move."
                        ),
                        url=f"{source_url}/videos/{offset + 1}",
                        asset=asset,
                        direction=direction,
                        confidence=confidence_from_text(title + description, engagement),
                        engagement_score=engagement,
                        observed_at=observed_at,
                        derived_return=deterministic_return(seed, direction),
                    )
                )
            traders.append(
                score_from_events(
                    display_name=name,
                    handle=handle,
                    platform="youtube",
                    source_url=source_url,
                    description=description,
                    style_tags=tags,
                    events=events,
                )
            )
        return SocialDiscoveryResult(
            provider=self.source_name,
            youtube_configured=False,
            traders=traders,
            warnings=[
                "YouTube Data API key is not configured, so BITprivat is running deterministic demo discovery.",
                "Managed trading remains paper-only until KYC, suitability, adviser, and venue controls are approved.",
            ],
        )


class YouTubeSocialDiscoveryProvider:
    source_name = "youtube-data-api"

    def __init__(
        self,
        *,
        api_key: str | None,
        queries: tuple[str, ...],
        channel_ids: tuple[str, ...],
        video_limit: int,
        timeout_seconds: int = 10,
    ) -> None:
        self.api_key = api_key
        self.queries = queries
        self.channel_ids = channel_ids
        self.video_limit = video_limit
        self.timeout_seconds = timeout_seconds

    def discover(self) -> SocialDiscoveryResult:
        if not self.api_key:
            return DemoSocialDiscoveryProvider().discover()

        warnings: list[str] = []
        try:
            search_items = self._search_videos()
            video_items = self._hydrate_videos(search_items)
            traders = self._aggregate_channels(video_items)
        except Exception as exc:
            fallback = DemoSocialDiscoveryProvider().discover()
            fallback.provider = self.source_name
            fallback.youtube_configured = True
            fallback.warnings = [
                f"YouTube Data API discovery failed ({exc.__class__.__name__}: {exc}); using deterministic fallback.",
                *fallback.warnings,
            ]
            return fallback

        if not traders:
            warnings.append("YouTube Data API returned no usable trading-analysis channels for the configured queries.")
        return SocialDiscoveryResult(
            provider=self.source_name,
            youtube_configured=True,
            traders=traders,
            warnings=warnings,
        )

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "key": self.api_key}
        request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "BITprivatSocialDiscovery/1.0"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _search_videos(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        max_results = min(50, max(3, self.video_limit))
        for query in self.queries:
            payload = self._get_json(
                "https://www.googleapis.com/youtube/v3/search",
                {
                    "part": "snippet",
                    "type": "video",
                    "order": "date",
                    "maxResults": max_results,
                    "q": query,
                },
            )
            items.extend(payload.get("items", []))
        for channel_id in self.channel_ids:
            payload = self._get_json(
                "https://www.googleapis.com/youtube/v3/search",
                {
                    "part": "snippet",
                    "type": "video",
                    "order": "date",
                    "maxResults": max_results,
                    "channelId": channel_id,
                },
            )
            items.extend(payload.get("items", []))

        seen: set[str] = set()
        unique_items: list[dict[str, Any]] = []
        for item in items:
            video_id = str(item.get("id", {}).get("videoId") or "")
            if video_id and video_id not in seen:
                seen.add(video_id)
                unique_items.append(item)
        return unique_items[: self.video_limit * max(1, len(self.queries) + len(self.channel_ids))]

    def _hydrate_videos(self, search_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ids = [str(item.get("id", {}).get("videoId")) for item in search_items if item.get("id", {}).get("videoId")]
        if not ids:
            return []
        hydrated: list[dict[str, Any]] = []
        for start in range(0, len(ids), 50):
            batch = ids[start : start + 50]
            payload = self._get_json(
                "https://www.googleapis.com/youtube/v3/videos",
                {
                    "part": "snippet,statistics",
                    "id": ",".join(batch),
                },
            )
            hydrated.extend(payload.get("items", []))
        return hydrated

    def _aggregate_channels(self, videos: list[dict[str, Any]]) -> list[DiscoveredSocialTrader]:
        by_channel: dict[str, list[dict[str, Any]]] = {}
        for video in videos:
            snippet = video.get("snippet", {})
            channel_id = str(snippet.get("channelId") or "")
            if channel_id:
                by_channel.setdefault(channel_id, []).append(video)

        traders: list[DiscoveredSocialTrader] = []
        for channel_id, channel_videos in by_channel.items():
            snippet = channel_videos[0].get("snippet", {})
            channel_title = str(snippet.get("channelTitle") or "YouTube Trader")
            handle = f"@{slugify(channel_title).replace('-', '')[:24]}"
            events = [self._event_from_video(video) for video in channel_videos]
            meaningful_events = [event for event in events if event.confidence >= 0.45]
            if not meaningful_events:
                continue
            source_url = f"https://www.youtube.com/channel/{channel_id}"
            assets = sorted({event.asset for event in meaningful_events})
            description = (
                f"YouTube-first social trader detected from {len(meaningful_events)} recent market videos. "
                f"Main coverage: {', '.join(assets[:4])}."
            )
            traders.append(
                score_from_events(
                    display_name=channel_title,
                    handle=handle,
                    platform="youtube",
                    source_url=source_url,
                    description=description,
                    style_tags=["youtube", "creator signals", "live monitoring"],
                    events=meaningful_events,
                )
            )
        return sorted(traders, key=lambda trader: trader.composite_score, reverse=True)

    def _event_from_video(self, video: dict[str, Any]) -> SocialEvidenceRecord:
        video_id = str(video.get("id") or "")
        snippet = video.get("snippet", {})
        statistics = video.get("statistics", {})
        title = str(snippet.get("title") or "Market update")
        description = str(snippet.get("description") or "")
        text = f"{title} {description}"
        view_count = safe_float(statistics.get("viewCount"))
        like_count = safe_float(statistics.get("likeCount"))
        engagement_score = clamp_value((math.log10(view_count + 10) / 7) * 0.75 + (math.log10(like_count + 3) / 6) * 0.25, 0.1, 0.98)
        direction = infer_direction(text)
        asset = extract_asset(text)
        summary = description.strip().replace("\n", " ")[:220] or f"YouTube market video covering {asset}."
        observed_at = str(snippet.get("publishedAt") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        return SocialEvidenceRecord(
            external_id=f"youtube-{video_id}",
            platform="youtube",
            title=title[:255],
            summary=summary,
            url=f"https://www.youtube.com/watch?v={video_id}",
            asset=asset,
            direction=direction,
            confidence=confidence_from_text(text, engagement_score),
            engagement_score=round(engagement_score, 3),
            observed_at=observed_at,
            derived_return=deterministic_return(f"{video_id}:{asset}:{direction}", direction),
        )


def safe_float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
