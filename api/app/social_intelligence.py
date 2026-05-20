from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html import unescape
import hashlib
import json
import math
import re
from typing import Any
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from .models import Direction, SocialPlatform


ASSET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "BTC": ("btc", "bitcoin"),
    "ETH": ("eth", "ethereum"),
    "SOL": ("sol", "solana"),
    "HYPE": ("hyperliquid", "hype"),
    "XRP": ("xrp", "ripple"),
    "DOGE": ("doge", "dogecoin"),
    "NVDA": ("nvda", "nvidia"),
    "TSLA": ("tsla", "tesla"),
    "GOLD": ("gold", "xau"),
    "DXY": ("dxy", "dollar index", "us dollar"),
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
    "liquidity",
    "rotation",
    "support",
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
    "liquidation",
    "resistance",
    "hedge",
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
    avatar_url: str | None = None,
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
        avatar_url=avatar_url,
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

    def discover(self, *, include_key_warning: bool = True) -> SocialDiscoveryResult:
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
        warnings = ["Managed trading remains paper-only until KYC, suitability, adviser, and venue controls are approved."]
        if include_key_warning:
            warnings.insert(0, "YouTube Data API key is not configured, so BITprivat is running deterministic demo discovery.")
        return SocialDiscoveryResult(provider=self.source_name, youtube_configured=False, traders=traders, warnings=warnings)

    def discover_target(
        self,
        target: str,
        video_limit: int | None = None,
        *,
        include_key_warning: bool = True,
    ) -> SocialDiscoveryResult:
        target_text = re.sub(r"\s+", " ", target or "").strip()
        normalized = target_text.lower().lstrip("@")
        result = self.discover(include_key_warning=include_key_warning)
        matches = [
            trader
            for trader in result.traders
            if normalized
            and normalized
            in " ".join(
                [
                    trader.display_name,
                    trader.handle,
                    trader.source_url,
                    trader.description,
                    " ".join(trader.primary_assets),
                    " ".join(trader.style_tags),
                ]
            ).lower()
        ]
        if not matches:
            matches = result.traders[:1]
            result.warnings.append(
                f"No exact demo match for '{target_text}', so BITprivat returned the closest deterministic trader profile."
            )
        limit = min(30, max(3, int(video_limit or 8)))
        for trader in matches:
            trader.evidence = trader.evidence[:limit]
        result.traders = matches
        return result


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
        self._public_channel_id_cache: dict[str, str | None] = {}

    def discover(self) -> SocialDiscoveryResult:
        if not self.api_key:
            return DemoSocialDiscoveryProvider().discover()

        warnings: list[str] = []
        try:
            search_items = self._search_videos()
            video_items = self._hydrate_videos(search_items)
            channel_meta = self._hydrate_channels(video_items)
            traders = self._aggregate_channels(video_items, channel_meta)
        except Exception as exc:
            fallback = DemoSocialDiscoveryProvider().discover(include_key_warning=False)
            fallback.provider = self.source_name
            fallback.youtube_configured = True
            fallback.warnings = [
                f"YouTube Data API discovery failed ({self._format_youtube_exception(exc)}); using deterministic fallback.",
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

    def discover_target(self, target: str, video_limit: int | None = None) -> SocialDiscoveryResult:
        cleaned_target = re.sub(r"\s+", " ", target or "").strip()
        if not cleaned_target:
            return SocialDiscoveryResult(
                provider=self.source_name,
                youtube_configured=bool(self.api_key),
                traders=[],
                warnings=["Enter a YouTube channel, video URL, @handle, or trader name before running analysis."],
            )
        limit = min(30, max(3, int(video_limit or self.video_limit)))
        if not self.api_key:
            try:
                public_traders = self._public_target_traders(cleaned_target, limit=limit)
            except Exception as exc:
                public_traders = []
                public_warning = (
                    "Public YouTube fallback failed "
                    f"({self._format_youtube_exception(exc)}); deterministic profile matching was used instead."
                )
            else:
                public_warning = None
            if public_traders:
                return SocialDiscoveryResult(
                    provider=self.source_name,
                    youtube_configured=False,
                    traders=public_traders,
                    warnings=[
                        "YouTube Data API key is not configured; used public YouTube metadata/RSS fallback with lower confidence.",
                    ],
                )
            fallback = DemoSocialDiscoveryProvider().discover_target(cleaned_target, video_limit=limit)
            fallback.provider = self.source_name
            fallback.youtube_configured = False
            if public_warning:
                fallback.warnings.insert(0, public_warning)
            return fallback

        warnings: list[str] = []
        try:
            videos = self._videos_from_target(cleaned_target, limit=limit)
            channel_meta = self._hydrate_channels(videos)
            traders = self._aggregate_channels(videos, channel_meta)
        except Exception as exc:
            return self._target_fallback_result(
                cleaned_target,
                limit=limit,
                reason=self._format_youtube_exception(exc),
            )

        if traders:
            warnings.append(
                f"Analyzed '{cleaned_target}' from up to {limit} latest public YouTube video(s); profile is ready for signal or managed-paper deployment."
            )
        else:
            fallback = self._target_fallback_result(
                cleaned_target,
                limit=limit,
                reason="official API returned no usable videos",
            )
            if fallback.traders:
                return fallback
            warnings.append(
                f"No usable public market-analysis videos were found for '{cleaned_target}'. Try a channel URL, @handle, or a more specific trader name."
            )
        return SocialDiscoveryResult(
            provider=self.source_name,
            youtube_configured=True,
            traders=traders,
            warnings=warnings,
        )

    def _target_fallback_result(self, target: str, *, limit: int, reason: str) -> SocialDiscoveryResult:
        public_warning: str | None = None
        try:
            public_traders = self._public_target_traders(target, limit=limit)
        except Exception as exc:
            public_traders = []
            public_warning = (
                "Public YouTube fallback also failed "
                f"({self._format_youtube_exception(exc)}); deterministic profile matching was used instead."
            )
        if public_traders:
            return SocialDiscoveryResult(
                provider=self.source_name,
                youtube_configured=bool(self.api_key),
                traders=public_traders,
                warnings=[
                    f"YouTube Data API target analysis failed ({reason}); used public YouTube metadata fallback for the supplied target.",
                    "Fallback metadata has lower confidence because it cannot read full statistics or channel history.",
                ],
            )
        fallback = DemoSocialDiscoveryProvider().discover_target(
            target,
            video_limit=limit,
            include_key_warning=not bool(self.api_key),
        )
        fallback.provider = self.source_name
        fallback.youtube_configured = bool(self.api_key)
        fallback.warnings = [
            f"YouTube target analysis failed ({reason}); using deterministic fallback.",
            *([public_warning] if public_warning else []),
            *fallback.warnings,
        ]
        return fallback

    def _public_target_traders(self, target: str, *, limit: int) -> list[DiscoveredSocialTrader]:
        video_trader = self._oembed_trader_from_target(target)
        if video_trader:
            return [video_trader]

        traders: list[DiscoveredSocialTrader] = []
        for channel_id in self._channel_ids_from_target(target):
            rss_trader = self._rss_trader_from_channel(channel_id, limit=limit)
            if rss_trader:
                traders.append(rss_trader)
        return sorted(traders, key=lambda trader: trader.composite_score, reverse=True)

    def _oembed_trader_from_target(self, target: str) -> DiscoveredSocialTrader | None:
        video_ids = self._video_ids_from_target(target)
        if not video_ids:
            return None
        watch_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
        payload = self._get_public_json(
            "https://www.youtube.com/oembed",
            {"url": watch_url, "format": "json"},
        )
        title = str(payload.get("title") or "YouTube market video")
        author_name = str(payload.get("author_name") or "YouTube Trader")
        author_url = str(payload.get("author_url") or "https://www.youtube.com")
        thumbnail_url = str(payload.get("thumbnail_url") or "") or None
        transcript = self._public_transcript_for_video(video_ids[0])
        text = " ".join(part for part in (title, author_name, transcript or "") if part)
        asset = extract_asset(text)
        direction = infer_direction(text)
        observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        engagement_score = 0.5 if transcript else 0.42
        event = SocialEvidenceRecord(
            external_id=f"youtube-oembed-{video_ids[0]}",
            platform="youtube",
            title=title[:255],
            summary=self._public_fallback_summary(asset, transcript),
            url=watch_url,
            asset=asset,
            direction=direction,
            confidence=confidence_from_text(text, engagement_score),
            engagement_score=engagement_score,
            observed_at=observed_at,
            derived_return=deterministic_return(f"oembed:{video_ids[0]}:{asset}:{direction}", direction),
        )
        return score_from_events(
            display_name=author_name,
            handle=f"@{slugify(author_name).replace('-', '')[:24]}",
            platform="youtube",
            source_url=author_url,
            avatar_url=thumbnail_url,
            description=(
                f"{author_name} was analyzed from a supplied YouTube video URL. "
                "The official YouTube Data API was unavailable, so BITprivat used public metadata fallback with conservative confidence."
            ),
            style_tags=["youtube", "public metadata fallback", "low confidence"],
            events=[event],
        )

    def _rss_trader_from_channel(self, channel_id: str, *, limit: int) -> DiscoveredSocialTrader | None:
        request = Request(
            f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
            headers={"User-Agent": "BITprivatSocialDiscovery/1.0"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            root = ET.fromstring(response.read())
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
            "media": "http://search.yahoo.com/mrss/",
        }
        display_name = root.findtext("atom:author/atom:name", default="YouTube Trader", namespaces=ns)
        source_url = root.findtext("atom:author/atom:uri", default=f"https://www.youtube.com/channel/{channel_id}", namespaces=ns)
        events: list[SocialEvidenceRecord] = []
        for entry in root.findall("atom:entry", ns)[:limit]:
            video_id = entry.findtext("yt:videoId", default="", namespaces=ns)
            title = entry.findtext("atom:title", default="YouTube market video", namespaces=ns)
            summary = entry.findtext("media:group/media:description", default="", namespaces=ns) or ""
            published = entry.findtext("atom:published", default="", namespaces=ns) or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            transcript = self._public_transcript_for_video(video_id)
            text = " ".join(part for part in (title, summary, transcript or "") if part)
            asset = extract_asset(text)
            direction = infer_direction(text)
            engagement_score = 0.46 if transcript else 0.38
            events.append(
                SocialEvidenceRecord(
                    external_id=f"youtube-rss-{video_id or hashlib.sha1(title.encode('utf-8')).hexdigest()[:12]}",
                    platform="youtube",
                    title=title[:255],
                    summary=self._rss_summary(asset, summary, transcript),
                    url=f"https://www.youtube.com/watch?v={video_id}" if video_id else source_url,
                    asset=asset,
                    direction=direction,
                    confidence=confidence_from_text(text, engagement_score),
                    engagement_score=engagement_score,
                    observed_at=published,
                    derived_return=deterministic_return(f"rss:{video_id}:{asset}:{direction}", direction),
                )
            )
        meaningful_events = [event for event in events if event.confidence >= 0.4]
        if not meaningful_events:
            return None
        return score_from_events(
            display_name=display_name,
            handle=f"@{slugify(display_name).replace('-', '')[:24]}",
            platform="youtube",
            source_url=source_url,
            description=(
                f"YouTube channel {display_name} was analyzed through public RSS fallback after the official API path was unavailable."
            ),
            style_tags=["youtube", "rss fallback", "recent videos"],
            events=meaningful_events,
        )

    def _get_public_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "BITprivatSocialDiscovery/1.0"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _format_youtube_exception(exc: Exception) -> str:
        if isinstance(exc, HTTPError):
            detail = ""
            try:
                raw = exc.read().decode("utf-8")
                payload = json.loads(raw)
                error = payload.get("error", {}) if isinstance(payload, dict) else {}
                message = str(error.get("message") or "").strip()
                errors = error.get("errors") or []
                reason = ""
                if errors and isinstance(errors[0], dict):
                    reason = str(errors[0].get("reason") or "").strip()
                status = str(error.get("status") or "").strip()
                detail = " ".join(part for part in (reason or status, message) if part)
            except Exception:
                detail = ""
            return f"HTTP {exc.code}{f' {detail}' if detail else ''}"
        return f"{exc.__class__.__name__}: {exc}"

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "key": self.api_key}
        request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "BITprivatSocialDiscovery/1.0"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _search_videos(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        max_results = min(50, max(3, self.video_limit))
        for query in self.queries:
            items.extend(self._search_videos_for_query(query, limit=max_results))
        for channel_id in self.channel_ids:
            items.extend(self._search_channel_videos(channel_id, limit=max_results))
        return self._dedupe_search_items(items)[: self.video_limit * max(1, len(self.queries) + len(self.channel_ids))]

    def _videos_from_target(self, target: str, *, limit: int) -> list[dict[str, Any]]:
        video_ids = self._video_ids_from_target(target)
        if video_ids:
            return self._hydrate_video_ids(video_ids[:limit])

        items: list[dict[str, Any]] = []
        channel_ids = self._channel_ids_from_target(target)
        if not channel_ids:
            channel_ids = self._search_channels(self._target_query(target), limit=3)
        for channel_id in channel_ids[:3]:
            items.extend(self._search_channel_videos(channel_id, limit=limit))
        if not items:
            items.extend(self._search_videos_for_query(self._target_query(target), limit=limit))
        return self._hydrate_videos(self._dedupe_search_items(items)[: limit * max(1, len(channel_ids) or 1)])

    def _search_videos_for_query(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        payload = self._get_json(
            "https://www.googleapis.com/youtube/v3/search",
            {
                "part": "snippet",
                "type": "video",
                "order": "date",
                "maxResults": min(50, max(3, limit)),
                "q": query,
            },
        )
        return list(payload.get("items", []))

    def _search_channel_videos(self, channel_id: str, *, limit: int) -> list[dict[str, Any]]:
        payload = self._get_json(
            "https://www.googleapis.com/youtube/v3/search",
            {
                "part": "snippet",
                "type": "video",
                "order": "date",
                "maxResults": min(50, max(3, limit)),
                "channelId": channel_id,
            },
        )
        return list(payload.get("items", []))

    def _search_channels(self, query: str, *, limit: int) -> list[str]:
        payload = self._get_json(
            "https://www.googleapis.com/youtube/v3/search",
            {
                "part": "snippet",
                "type": "channel",
                "order": "relevance",
                "maxResults": min(10, max(1, limit)),
                "q": query,
            },
        )
        channel_ids: list[str] = []
        for item in payload.get("items", []):
            channel_id = str(item.get("id", {}).get("channelId") or "")
            if channel_id and channel_id not in channel_ids:
                channel_ids.append(channel_id)
        return channel_ids

    @staticmethod
    def _dedupe_search_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        unique_items: list[dict[str, Any]] = []
        for item in items:
            video_id = str(item.get("id", {}).get("videoId") or "")
            if video_id and video_id not in seen:
                seen.add(video_id)
                unique_items.append(item)
        return unique_items

    def _hydrate_videos(self, search_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ids = [str(item.get("id", {}).get("videoId")) for item in search_items if item.get("id", {}).get("videoId")]
        return self._hydrate_video_ids(ids)

    def _hydrate_video_ids(self, ids: list[str]) -> list[dict[str, Any]]:
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

    @staticmethod
    def _parse_maybe_youtube_url(target: str):
        candidate = target.strip()
        if "youtube.com" not in candidate and "youtu.be" not in candidate:
            return None
        if "://" not in candidate:
            candidate = f"https://{candidate}"
        return urlparse(candidate)

    def _video_ids_from_target(self, target: str) -> list[str]:
        parsed = self._parse_maybe_youtube_url(target)
        if not parsed:
            return []
        query_video = parse_qs(parsed.query).get("v", [""])[0]
        if query_video:
            return [query_video]
        segments = [segment for segment in parsed.path.split("/") if segment]
        if parsed.netloc.endswith("youtu.be") and segments:
            return [segments[0]]
        for marker in ("shorts", "embed", "live"):
            if marker in segments:
                index = segments.index(marker)
                if len(segments) > index + 1:
                    return [segments[index + 1]]
        return []

    def _channel_ids_from_target(self, target: str) -> list[str]:
        candidate = target.strip()
        if re.fullmatch(r"UC[a-zA-Z0-9_-]{10,}", candidate):
            return [candidate]
        parsed = self._parse_maybe_youtube_url(candidate)
        if parsed:
            segments = [segment for segment in parsed.path.split("/") if segment]
            if "channel" in segments:
                index = segments.index("channel")
                if len(segments) > index + 1 and segments[index + 1].startswith("UC"):
                    return [segments[index + 1]]

        public_channel_id = self._resolve_public_channel_id(candidate)
        if public_channel_id:
            return [public_channel_id]
        return []

    def _resolve_public_channel_id(self, target: str) -> str | None:
        lookup_url = self._public_channel_lookup_url(target)
        if not lookup_url:
            return None
        if lookup_url in self._public_channel_id_cache:
            return self._public_channel_id_cache[lookup_url]
        try:
            html = self._fetch_public_text(lookup_url)
            channel_id = self._extract_public_channel_id(html)
        except Exception:
            channel_id = None
        if channel_id:
            self._public_channel_id_cache[lookup_url] = channel_id
        return channel_id

    def _public_channel_lookup_url(self, target: str) -> str | None:
        candidate = target.strip()
        if not candidate:
            return None
        if candidate.startswith("@") and " " not in candidate:
            return f"https://www.youtube.com/{candidate}"

        parsed = self._parse_maybe_youtube_url(candidate)
        if not parsed:
            return None
        segments = [segment for segment in parsed.path.split("/") if segment]
        if not segments:
            return None
        if segments[0].startswith("@"):
            return f"https://www.youtube.com/{segments[0]}"
        if segments[0] in {"c", "user"} and len(segments) > 1:
            return f"https://www.youtube.com/{segments[0]}/{segments[1]}"
        return None

    def _fetch_public_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": "BITprivatSocialDiscovery/1.0"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read(1_000_000).decode("utf-8", errors="ignore")

    def _public_transcript_for_video(self, video_id: str) -> str | None:
        if not video_id:
            return None
        try:
            track_list_url = f"https://video.google.com/timedtext?{urlencode({'type': 'list', 'v': video_id})}"
            track_list = self._fetch_public_text(track_list_url)
            root = ET.fromstring(track_list)
            tracks = root.findall("track")
            if not tracks:
                return None
            selected = next(
                (
                    track
                    for track in tracks
                    if str(track.attrib.get("lang_code") or "").lower().startswith("en")
                ),
                tracks[0],
            )
            params = {
                "v": video_id,
                "lang": selected.attrib.get("lang_code") or "en",
            }
            if selected.attrib.get("name"):
                params["name"] = selected.attrib["name"]
            transcript_xml = self._fetch_public_text(f"https://video.google.com/timedtext?{urlencode(params)}")
            transcript_root = ET.fromstring(transcript_xml)
            parts = [
                unescape("".join(node.itertext()))
                for node in transcript_root.iter()
                if node.tag in {"text", "p"} and "".join(node.itertext()).strip()
            ]
            return self._clean_transcript_text(" ".join(parts))
        except Exception:
            return None

    @staticmethod
    def _clean_transcript_text(value: str, *, limit: int = 3200) -> str | None:
        cleaned = re.sub(r"\s+", " ", unescape(value or "")).strip()
        if not cleaned:
            return None
        return cleaned[:limit]

    @staticmethod
    def _public_fallback_summary(asset: str, transcript: str | None) -> str:
        if transcript:
            return f"Public YouTube fallback used available captions/transcript for {asset}: {transcript[:180]}"
        return (
            "Public YouTube metadata fallback extracted the video title and creator after the official API path failed. "
            f"Use this as a low-confidence signal for {asset}."
        )

    @staticmethod
    def _rss_summary(asset: str, summary: str, transcript: str | None) -> str:
        if transcript:
            return f"Public RSS plus available captions/transcript covering {asset}: {transcript[:180]}"
        return summary[:190] or f"Public RSS fallback video covering {asset}."

    @staticmethod
    def _extract_public_channel_id(html: str) -> str | None:
        patterns = (
            r'"channelId"\s*:\s*"(UC[a-zA-Z0-9_-]{10,})"',
            r'"externalId"\s*:\s*"(UC[a-zA-Z0-9_-]{10,})"',
            r'itemprop="channelId"\s+content="(UC[a-zA-Z0-9_-]{10,})"',
            r"youtube\.com/channel/(UC[a-zA-Z0-9_-]{10,})",
        )
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return None

    def _target_query(self, target: str) -> str:
        parsed = self._parse_maybe_youtube_url(target)
        if parsed:
            segments = [segment for segment in parsed.path.split("/") if segment]
            for segment in reversed(segments):
                if segment not in {"c", "user", "channel", "watch", "videos"} and not segment.startswith("UC"):
                    return re.sub(r"[@_-]+", " ", segment).strip() or target
        return re.sub(r"\s+", " ", target.lstrip("@").replace("_", " ").replace("-", " ")).strip()

    def _hydrate_channels(self, videos: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        channel_ids = sorted(
            {
                str(video.get("snippet", {}).get("channelId") or "")
                for video in videos
                if video.get("snippet", {}).get("channelId")
            }
        )
        if not channel_ids:
            return {}
        metadata: dict[str, dict[str, Any]] = {}
        for start in range(0, len(channel_ids), 50):
            batch = channel_ids[start : start + 50]
            payload = self._get_json(
                "https://www.googleapis.com/youtube/v3/channels",
                {
                    "part": "snippet,statistics",
                    "id": ",".join(batch),
                },
            )
            for item in payload.get("items", []):
                channel_id = str(item.get("id") or "")
                if channel_id:
                    metadata[channel_id] = item
        return metadata

    def _aggregate_channels(
        self,
        videos: list[dict[str, Any]],
        channel_meta: dict[str, dict[str, Any]] | None = None,
    ) -> list[DiscoveredSocialTrader]:
        by_channel: dict[str, list[dict[str, Any]]] = {}
        for video in videos:
            snippet = video.get("snippet", {})
            channel_id = str(snippet.get("channelId") or "")
            if channel_id:
                by_channel.setdefault(channel_id, []).append(video)

        traders: list[DiscoveredSocialTrader] = []
        for channel_id, channel_videos in by_channel.items():
            snippet = channel_videos[0].get("snippet", {})
            meta_snippet = (channel_meta or {}).get(channel_id, {}).get("snippet", {})
            channel_title = str(meta_snippet.get("title") or snippet.get("channelTitle") or "YouTube Trader")
            channel_description = str(meta_snippet.get("description") or "")
            thumbnails = meta_snippet.get("thumbnails", {}) if isinstance(meta_snippet, dict) else {}
            avatar_url = self._best_thumbnail_url(thumbnails)
            handle = f"@{slugify(channel_title).replace('-', '')[:24]}"
            events = [self._event_from_video(video) for video in channel_videos]
            meaningful_events = [event for event in events if event.confidence >= 0.45]
            if not meaningful_events:
                continue
            source_url = f"https://www.youtube.com/channel/{channel_id}"
            assets = sorted({event.asset for event in meaningful_events})
            description = (
                (channel_description[:180] + " " if channel_description else "")
                + f"YouTube-first social trader detected from {len(meaningful_events)} recent market videos. "
                + f"Main coverage: {', '.join(assets[:4])}. "
                + "Analysis uses video title, description, engagement, and recency."
            )
            traders.append(
                score_from_events(
                    display_name=channel_title,
                    handle=handle,
                    platform="youtube",
                    source_url=source_url,
                    avatar_url=avatar_url,
                    description=description,
                    style_tags=["youtube", "creator signals", "live monitoring"],
                    events=meaningful_events,
                )
            )
        return sorted(traders, key=lambda trader: trader.composite_score, reverse=True)

    @staticmethod
    def _best_thumbnail_url(thumbnails: dict[str, Any]) -> str | None:
        for key in ("high", "medium", "default"):
            candidate = thumbnails.get(key, {}) if isinstance(thumbnails, dict) else {}
            url = candidate.get("url") if isinstance(candidate, dict) else None
            if url:
                return str(url)
        return None

    def _event_from_video(self, video: dict[str, Any]) -> SocialEvidenceRecord:
        video_id = str(video.get("id") or "")
        snippet = video.get("snippet", {})
        statistics = video.get("statistics", {})
        title = str(snippet.get("title") or "Market update")
        description = str(snippet.get("description") or "")
        transcript = self._public_transcript_for_video(video_id)
        text = " ".join(part for part in (title, description, transcript or "") if part)
        view_count = safe_float(statistics.get("viewCount"))
        like_count = safe_float(statistics.get("likeCount"))
        engagement_score = clamp_value((math.log10(view_count + 10) / 7) * 0.75 + (math.log10(like_count + 3) / 6) * 0.25, 0.1, 0.98)
        direction = infer_direction(text)
        asset = extract_asset(text)
        title_terms = self._matched_title_terms(title)
        title_note = f" Title match: {', '.join(title_terms[:4])}." if title_terms else ""
        if transcript:
            summary = f"Caption-enriched video covering {asset}: {transcript[:170]}{title_note}".strip()
        else:
            summary = (description.strip().replace("\n", " ")[:190] + title_note).strip() or f"YouTube market video covering {asset}.{title_note}"
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

    def _matched_title_terms(self, title: str) -> list[str]:
        lowered = title.lower()
        terms: list[str] = []
        for query in self.queries:
            for token in re.findall(r"[a-zA-Z0-9]{3,}", query.lower()):
                if token in lowered and token not in terms:
                    terms.append(token)
        return terms


def safe_float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
