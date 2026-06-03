from __future__ import annotations

from dataclasses import dataclass
import re

from .models import (
    ExtractedFinancialSignal,
    FinancialSignalAssetType,
    FinancialSignalClaimType,
    FinancialSignalDirection,
    FinancialSignalExtractionRequest,
    FinancialSignalExtractionResult,
    FinancialSignalHorizon,
)


FINANCIAL_SIGNAL_EXTRACTOR_PROMPT_VERSION = "financial-signal-extractor-v1.0"

FINANCIAL_SIGNAL_EXTRACTION_SYSTEM_PROMPT = """You are a financial-signal extraction engine for BITprivat. Your only job is to
read a video transcript from a trading/finance content creator and extract
discrete, structured market claims as JSON. You do not give opinions, advice, or
commentary. You return JSON only - no prose, no markdown.

INPUT
You receive: the transcript text, the video_id, the channel_id, the video's
publish timestamp (video_publish_ts, ISO-8601 UTC), and the language code.

OUTPUT
Return exactly one JSON object matching this shape:

{
  "video_id": string,
  "channel_id": string,
  "video_publish_ts": string,
  "language": string,
  "signals": [ Signal, ... ]
}

Each Signal:
{
  "asset": string,
  "asset_type": "crypto"|"equity"|"index"|"commodity"|"fx",
  "direction": "long"|"short"|"neutral",
  "claim_type": "tradeable"|"commentary"|"educational",
  "conviction": number,
  "horizon": "intraday"|"swing"|"multiweek",
  "horizon_hours": integer,
  "entry": number|null,
  "target": number|null,
  "invalidation": number|null,
  "is_personal_position": boolean,
  "evidence_quote": string,
  "evidence_timestamp_sec": integer,
  "extractor_confidence": number
}

RULES
1. Extract ONLY from the transcript body. Ignore the title and any thumbnail text.
2. Map each claim to a canonical asset symbol. Normalize names: "Bitcoin"->"BTC",
   "Nasdaq"->"NDX","S&P"->"SPX","Nifty"->"NIFTY","Gold"->"GOLD". If the asset is
   unclear or not a real tradeable instrument, skip the claim.
3. claim_type:
   - "tradeable": a specific directional call a person could act on.
   - "commentary": general market opinion or vibe with no actionable setup.
   - "educational": teaching, definitions, recaps, or historical examples.
   When uncertain between tradeable and commentary, choose "commentary".
4. direction "neutral" is allowed only for explicit "wait / no trade / chop" views.
5. conviction reflects the CREATOR's commitment. extractor_confidence reflects parser certainty.
6. Levels: include entry/target/invalidation only if explicitly stated as numbers.
   Never invent or estimate levels. Use null when not stated.
7. horizon: infer from language. Use 24 / 168 / 720 hours unless a specific timeframe is stated.
8. evidence_quote must be copied verbatim from the transcript and be 30 words or fewer.
9. Do not merge multiple assets into one signal. One asset + one direction per signal.
10. If the transcript contains no actionable or commentary market claims, return "signals": [].
11. Output valid JSON only. No explanations, no trailing text, no markdown fences."""


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    text: str
    timestamp_sec: int
    explicit_timestamp: bool


ASSET_CATALOG: dict[str, tuple[FinancialSignalAssetType, tuple[str, ...]]] = {
    "BTC": ("crypto", ("btc", "bitcoin")),
    "ETH": ("crypto", ("eth", "ethereum")),
    "SOL": ("crypto", ("sol", "solana")),
    "XRP": ("crypto", ("xrp", "ripple")),
    "DOGE": ("crypto", ("doge", "dogecoin")),
    "HYPE": ("crypto", ("hype", "hyperliquid")),
    "BNB": ("crypto", ("bnb", "binance coin")),
    "SPX": ("index", ("spx", "s&p", "s&p 500", "s and p", "spy")),
    "NDX": ("index", ("ndx", "nasdaq", "qqq", "nasdaq 100")),
    "NIFTY": ("index", ("nifty", "nifty 50")),
    "DXY": ("index", ("dxy", "dollar index")),
    "GOLD": ("commodity", ("gold", "xau", "xauusd")),
    "SILVER": ("commodity", ("silver", "xag", "xagusd")),
    "OIL": ("commodity", ("oil", "crude", "wti", "brent")),
    "EURUSD": ("fx", ("eurusd", "eur/usd", "euro dollar")),
    "GBPUSD": ("fx", ("gbpusd", "gbp/usd", "pound dollar")),
    "USDJPY": ("fx", ("usdjpy", "usd/jpy", "dollar yen")),
    "NVDA": ("equity", ("nvda", "nvidia")),
    "TSLA": ("equity", ("tsla", "tesla")),
    "AAPL": ("equity", ("aapl", "apple stock")),
    "MSFT": ("equity", ("msft", "microsoft")),
}

LONG_TERMS = (
    "accumulate",
    "breakout",
    "buy",
    "buying",
    "bullish",
    "go long",
    "going higher",
    "higher",
    "long",
    "rally",
    "risk on",
    "upside",
)
SHORT_TERMS = (
    "bearish",
    "breakdown",
    "crash",
    "downside",
    "go short",
    "going lower",
    "lower",
    "sell",
    "selling",
    "short",
    "shorting",
)
NEUTRAL_TERMS = (
    "chop",
    "do not trade",
    "flat",
    "no trade",
    "range bound",
    "stay out",
    "wait",
)
TRADEABLE_TERMS = (
    "buy here",
    "buying here",
    "entry",
    "i am buying",
    "i am long",
    "i am short",
    "i bought",
    "i hold",
    "i own",
    "i'm buying",
    "i'm long",
    "i'm short",
    "invalidation",
    "invalidated",
    "long here",
    "my position",
    "short here",
    "stop",
    "stop loss",
    "take profit",
    "target",
)
HEDGED_TERMS = ("could", "maybe", "might", "possibly", "if", "watching", "not sure")
HIGH_CONVICTION_TERMS = ("all in", "high conviction", "strong conviction", "clear setup", "must hold", "i am buying", "i'm buying")
EDUCATIONAL_TERMS = ("definition", "educational", "explaining", "history", "historically", "how to", "lesson", "means", "tutorial")


def extract_financial_signals_from_transcript(
    payload: FinancialSignalExtractionRequest,
) -> FinancialSignalExtractionResult:
    signals: list[ExtractedFinancialSignal] = []
    seen: set[tuple[str, str, str, str]] = set()

    for segment in split_transcript_segments(payload.transcript):
        for sentence in split_claim_sentences(segment.text):
            for asset, asset_type in assets_in_text(sentence):
                signal = extract_signal_from_sentence(sentence, asset, asset_type, segment)
                if signal is None:
                    continue
                key = (signal.asset, signal.direction, signal.claim_type, signal.evidence_quote.lower())
                if key in seen:
                    continue
                seen.add(key)
                signals.append(signal)

    return FinancialSignalExtractionResult(
        video_id=payload.video_id,
        channel_id=payload.channel_id,
        video_publish_ts=payload.video_publish_ts,
        language=payload.language,
        signals=signals,
    )


def split_transcript_segments(transcript: str) -> list[TranscriptSegment]:
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    segments: list[TranscriptSegment] = []
    for line in lines:
        parsed = parse_timestamped_line(line)
        if parsed:
            timestamp, text = parsed
            if text:
                segments.append(TranscriptSegment(text=text, timestamp_sec=timestamp, explicit_timestamp=True))
    if segments:
        return segments

    cleaned = re.sub(r"\s+", " ", transcript).strip()
    return [TranscriptSegment(text=cleaned, timestamp_sec=0, explicit_timestamp=False)] if cleaned else []


def parse_timestamped_line(line: str) -> tuple[int, str] | None:
    match = re.match(
        r"^\s*(?:\[(?P<bracket>\d{1,2}:\d{2}(?::\d{2})?)\]|\(?(?P<plain>\d{1,2}:\d{2}(?::\d{2})?)\)?)\s*[-:]?\s*(?P<text>.*)$",
        line,
    )
    if not match:
        return None
    timestamp_text = match.group("bracket") or match.group("plain")
    return timestamp_to_seconds(timestamp_text), re.sub(r"\s+", " ", match.group("text") or "").strip()


def timestamp_to_seconds(value: str) -> int:
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def split_claim_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def assets_in_text(text: str) -> list[tuple[str, FinancialSignalAssetType]]:
    lowered = f" {text.lower()} "
    matches: list[tuple[str, FinancialSignalAssetType]] = []
    for asset, (asset_type, aliases) in ASSET_CATALOG.items():
        if any(alias_matches(lowered, alias) for alias in aliases):
            matches.append((asset, asset_type))
    return matches


def alias_matches(lowered_text: str, alias: str) -> bool:
    escaped = re.escape(alias.lower())
    if alias.isalpha() and len(alias) <= 5:
        return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", lowered_text) is not None
    return alias.lower() in lowered_text


def extract_signal_from_sentence(
    sentence: str,
    asset: str,
    asset_type: FinancialSignalAssetType,
    segment: TranscriptSegment,
) -> ExtractedFinancialSignal | None:
    direction = infer_financial_direction(sentence)
    claim_type = infer_claim_type(sentence, direction)
    if claim_type is None:
        return None
    if claim_type != "educational" and direction == "neutral" and not has_any(sentence, NEUTRAL_TERMS):
        return None

    quote = evidence_quote(sentence)
    if not quote:
        return None
    horizon, horizon_hours = infer_horizon(sentence)
    entry = extract_level(sentence, ("entry", "enter", "buy at", "long at", "short at", "around"))
    target = extract_level(sentence, ("target", "take profit", "tp", "resistance", "to", "toward"))
    invalidation = extract_level(sentence, ("invalidation", "invalidated", "stop", "stop loss", "below", "under", "above"))
    is_tradeable = claim_type == "tradeable"
    return ExtractedFinancialSignal(
        asset=asset,
        asset_type=asset_type,
        direction=direction,
        claim_type=claim_type,
        conviction=creator_conviction(sentence, claim_type),
        horizon=horizon,
        horizon_hours=horizon_hours,
        entry=entry if is_tradeable else None,
        target=target if is_tradeable else None,
        invalidation=invalidation if is_tradeable else None,
        is_personal_position=is_personal_position(sentence),
        evidence_quote=quote,
        evidence_timestamp_sec=segment.timestamp_sec,
        extractor_confidence=extractor_confidence(sentence, claim_type, segment.explicit_timestamp, entry, target, invalidation),
    )


def infer_financial_direction(text: str) -> FinancialSignalDirection:
    lowered = text.lower()
    if has_any(lowered, NEUTRAL_TERMS):
        return "neutral"
    long_score = sum(1 for term in LONG_TERMS if term in lowered)
    short_score = sum(1 for term in SHORT_TERMS if term in lowered)
    if long_score > short_score:
        return "long"
    if short_score > long_score:
        return "short"
    return "neutral"


def infer_claim_type(text: str, direction: FinancialSignalDirection) -> FinancialSignalClaimType | None:
    lowered = text.lower()
    if direction in {"long", "short"}:
        return "tradeable" if has_any(lowered, TRADEABLE_TERMS) else "commentary"
    if has_any(lowered, NEUTRAL_TERMS):
        return "commentary"
    if has_any(lowered, EDUCATIONAL_TERMS):
        return "educational"
    return None


def infer_horizon(text: str) -> tuple[FinancialSignalHorizon, int]:
    lowered = text.lower()
    specific = re.search(r"(?:next|for|in)\s+(\d{1,3})\s*(hour|hours|day|days|week|weeks|month|months)", lowered)
    if specific:
        amount = int(specific.group(1))
        unit = specific.group(2)
        multiplier = 1 if unit.startswith("hour") else 24 if unit.startswith("day") else 168 if unit.startswith("week") else 720
        hours = max(1, amount * multiplier)
        if hours <= 36:
            return "intraday", hours
        if hours <= 240:
            return "swing", hours
        return "multiweek", hours
    if has_any(lowered, ("scalp", "today", "intraday", "next session", "this session")):
        return "intraday", 24
    if has_any(lowered, ("this week", "swing", "few days", "next week")):
        return "swing", 168
    if has_any(lowered, ("cycle", "this month", "next month", "multiweek", "quarter", "into year end")):
        return "multiweek", 720
    return "swing", 168


def extract_level(text: str, markers: tuple[str, ...]) -> float | None:
    lowered = text.lower()
    for marker in markers:
        index = lowered.find(marker)
        if index < 0:
            continue
        window = text[index : index + 72]
        match = re.search(r"\$?\b\d+(?:,\d{3})*(?:\.\d+)?\s*[kKmM]?\b", window)
        if match:
            return parse_level_number(match.group(0))
    return None


def parse_level_number(raw: str) -> float | None:
    cleaned = raw.replace("$", "").replace(",", "").strip()
    multiplier = 1.0
    if cleaned.lower().endswith("k"):
        multiplier = 1000.0
        cleaned = cleaned[:-1]
    elif cleaned.lower().endswith("m"):
        multiplier = 1_000_000.0
        cleaned = cleaned[:-1]
    try:
        return round(float(cleaned) * multiplier, 8)
    except ValueError:
        return None


def creator_conviction(text: str, claim_type: FinancialSignalClaimType) -> float:
    lowered = text.lower()
    score = 0.58 if claim_type == "tradeable" else 0.42 if claim_type == "commentary" else 0.26
    score += 0.18 if has_any(lowered, HIGH_CONVICTION_TERMS) else 0.0
    score -= 0.16 if has_any(lowered, HEDGED_TERMS) else 0.0
    score += 0.08 if has_any(lowered, ("target", "stop", "invalidation", "entry")) else 0.0
    return round(clamp(score, 0.05, 0.98), 2)


def extractor_confidence(
    text: str,
    claim_type: FinancialSignalClaimType,
    explicit_timestamp: bool,
    entry: float | None,
    target: float | None,
    invalidation: float | None,
) -> float:
    score = 0.66 if claim_type == "tradeable" else 0.58 if claim_type == "commentary" else 0.5
    score += 0.08 if explicit_timestamp else -0.06
    score += 0.06 if any(level is not None for level in (entry, target, invalidation)) else 0.0
    score -= 0.08 if has_any(text.lower(), HEDGED_TERMS) else 0.0
    return round(clamp(score, 0.25, 0.96), 2)


def is_personal_position(text: str) -> bool:
    lowered = text.lower()
    personal_terms = (
        "i am buying",
        "i am long",
        "i am short",
        "i bought",
        "i hold",
        "i own",
        "i'm buying",
        "i'm long",
        "i'm short",
        "my position",
        "personally long",
        "personally short",
    )
    return has_any(lowered, personal_terms)


def evidence_quote(sentence: str) -> str:
    cleaned = re.sub(r"\s+", " ", sentence).strip()
    cleaned = re.sub(r"^\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*[-:]?\s*", "", cleaned).strip()
    words = cleaned.split()
    if not words:
        return ""
    return " ".join(words[:30])


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
