"""
OpenQuant-FNO: Low-Latency Regex Ingestion & Normalizer
======================================================
Pre-compiled, microsecond-optimized regular expressions extracting Indian F&O option
trade parameters from unstructured, noisy Telegram alerts.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class NormalizedSignal:
    raw_text: str
    action: str                        # "ENTRY", "TARGET_HIT", "SL_HIT", "UNKNOWN"
    underlying: Optional[str] = None   # "NIFTY", "BANKNIFTY", "FINNIFTY", etc.
    strike: Optional[int] = None       # e.g., 22500, 48000
    option_type: Optional[str] = None  # "CE" or "PE"
    instrument: Optional[str] = None   # e.g. "BANKNIFTY 48000 CE"
    entry_price: float = 0.0
    stop_loss: float = 0.0
    targets: List[float] = field(default_factory=list)
    exit_price: float = 0.0
    target_tier: Optional[int] = None  # e.g. 1 for T1, 2 for T2
    confidence: float = 1.0            # Parse confidence
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "action": self.action,
            "underlying": self.underlying,
            "strike": self.strike,
            "option_type": self.option_type,
            "instrument": self.instrument,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "targets": self.targets,
            "exit_price": self.exit_price,
            "target_tier": self.target_tier,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat()
        }


# ==============================================================================
# Pre-Compiled High Performance Regex Patterns
# ==============================================================================

def infer_underlying(strike: int) -> str:
    """Infers the underlying index from the option strike level."""
    if 15000 <= strike <= 35000:
        return "NIFTY"
    elif 40000 <= strike <= 65000:
        return "BANKNIFTY"
    elif 65000 < strike <= 95000:
        return "SENSEX"
    elif 8000 <= strike <= 14000:
        return "MIDCPNIFTY"
    return "NIFTY"


# Pattern 1: Instrument, Strike & Option Type
# Matches: "BANKNIFTY 48000 CE", "NIFTY 29 Sept 23200 Put", "NIFTY50 : 23250 PUT", "23700 call"
RE_INSTRUMENT = re.compile(
    r"\b(?:(BANK\s?NIFTY|FIN\s?NIFTY|MIDCP\s?NIFTY|NIFTY\s?50|NIFTY|SENSEX)\b"
    r"(?:[^\d\n]*\b(?:\d{1,2}\s*[A-Za-z]{3,4})[^\d\n]*)?[\s:]*)?"
    r"(\d{4,5})\s*(CE|PE|CALL|PUT)\b",
    re.IGNORECASE
)

# Alternative Pattern: When Strike and Option Type come first: "48000 CE BANKNIFTY" or "48000 CE"
RE_INSTRUMENT_ALT = re.compile(
    r"\b(\d{4,5})\s*(CE|PE|CALL|PUT)(?:\s*(BANK\s?NIFTY|FIN\s?NIFTY|MIDCP\s?NIFTY|NIFTY\s?50|NIFTY|SENSEX))?\b",
    re.IGNORECASE
)

# Target Hit / Profit Booking patterns (e.g. "Target 1 done", "Done and Dusted", "150₹ Too 181₹+", "T1 hit")
RE_TARGET_HIT = re.compile(
    r"(?:TARGET\s*(\d+)?\s*(?:HIT|DONE|ACHIEVED|OBLITERATED)|TGT\s*(\d+)?\s*(?:HIT|DONE|ACHIEVED)|"
    r"TAG\s*(\d+)?\s*(?:HIT|DONE|ACHIEVED)|"
    r"(?:FIRST|1ST|SECOND|2ND|THIRD|3RD|ALL|FULL)\s*TARGETS?\s*(?:HIT|DONE|ACHIEVED|OBLITERATED)|"
    r"T([1-9])\s*(?:DONE|HIT|ACHIEVED)|"
    r"DONE\s*AND\s*DUSTED|"
    r"BOOK\s*(?:PROFIT|PARTIAL|FULL|50%|HALF|KR|KAR|ACCORDINGLY)|"
    r"JISS\s*KO\s*BOOK|"
    r"\b(\d{2,5})\s*CMP.*?BOOK|"
    r"\b(\d{2,5})\s*(?:😍|😎|🔥|🚀|💥|blast|boom)|"
    r"\b(\d{2,5})\s*[₹]?\s*TOO\s*(\d{2,5})\s*[₹]?|"
    r"ALL\s*TARGETS?\s*(?:HIT|ACHIEVED|DONE)|ROCKING|BOOM|BLAST)",
    re.IGNORECASE
)

# Stop Loss Hit patterns
RE_SL_HIT = re.compile(
    r"(?:SL\s*HIT|STOPLOSS\s*HIT|STOP\s*LOSS\s*HIT|EXIT\s*SL|EXIT\s*AT\s*SL|TRAILING\s*SL\s*HIT)",
    re.IGNORECASE
)

# Entry keywords
RE_ENTRY_ACTION = re.compile(
    r"\b(BUY|ENTRY|LONG|BUY\s*ABOVE|BUY\s*AT|ABOVE|CMP|ENTER|TRADE|BUYING)\b|@",
    re.IGNORECASE
)

# Entry Price Extraction
RE_ENTRY_PRICE = re.compile(
    r"(?:ABOVE|BUY\s*(?:ABOVE|AT|AROUND)?|ENTRY|CMP|PRICE|@|NEAR|BUYING)[\s:=]*[₹\s]*([\d]{1,5}(?:\.\d{1,2})?)",
    re.IGNORECASE
)

# Range Entry: e.g. "BUY AT 200 - 205" or "200-210"
RE_ENTRY_RANGE = re.compile(
    r"(?:BUY|ENTRY|AT|ABOVE)?\s*[₹\s]*(\d{2,5}(?:\.\d+)?)\s*[-–—]\s*[₹\s]*(\d{2,5}(?:\.\d+)?)",
    re.IGNORECASE
)

# Stop Loss Extraction
RE_STOP_LOSS = re.compile(
    r"(?:SL|STOP\s*LOSS|STOPLOSS|STOP)[\s:=]*[₹\s]*([\d]{1,5}(?:\.\d{1,2})?)",
    re.IGNORECASE
)

# Exit / Hit Price
RE_EXIT_PRICE = re.compile(
    r"(?:AT|CMP|EXIT\s*AT|BOOK\s*AT|HIGH\s*MADE|NOW\s*AT|CURRENT)[\s:=]*[₹\s]*([\d]{1,5}(?:\.\d{1,2})?)|"
    r"TOO\s*[₹\s]*([\d]{2,5})|"
    r"\b([\d]{2,5})\s*(?:CMP|😍|😎|🔥|🚀|💥|blast|boom)",
    re.IGNORECASE
)

# Multi-tier Target Patterns (e.g. "TARGET 1: 240", "TARGET: 240/260", "TGT- 240", "TAG 28/35/80/120")
RE_TARGET_KEYWORD = re.compile(
    r"(?:TARGETS?|TGTS?|TAGS?|TP)[\s:=]*([\d\s,./\-|–—+₹]+)",
    re.IGNORECASE
)

# Specific Tiered Target Extractor (e.g. "T1: 170 T2: 200" or "TARGET 1: 170 TARGET 2: 200")
RE_TIERED_TARGETS = re.compile(
    r"(?:TARGET\s*[1-9]|TGT\s*[1-9]|T[1-9])\s*[:=\-]\s*([\d]{2,5}(?:\.\d{1,2})?)",
    re.IGNORECASE
)


def _clean_text(text: str) -> str:
    """Normalizes whitespace and replaces special Unicode hyphens/quotes."""
    if not text:
        return ""
    text = text.replace('\xa0', ' ').replace('\u200b', ' ')
    text = re.sub(r'[\r\n]+', ' ', text)
    return text.strip()


def parse_targets(targets_raw: str, entry_price: float = 0.0) -> List[float]:
    """
    Extracts a sorted list of numeric target price levels from formats like:
    - "240/260/280"
    - "T1: 240, T2: 260, T3: 300"
    - "28/35/5/80/120"
    """
    if not targets_raw:
        return []

    # Extract all floating point or integer numbers
    raw_numbers = re.findall(r"\b\d{1,5}(?:\.\d{1,2})?\b", targets_raw)
    targets = []
    for num_str in raw_numbers:
        try:
            val = float(num_str)
            if val > 0 and val not in targets:
                # Target should be above entry price
                if entry_price > 0 and val <= entry_price:
                    continue
                targets.append(val)
        except ValueError:
            continue

    targets.sort()
    return targets


def parse_signal(text: str, ocr_text: str = "") -> Optional[NormalizedSignal]:
    """
    Parses an incoming raw Telegram message into a NormalizedSignal.
    Returns None if the message does not match any actionable trading signal.
    """
    if not text or not isinstance(text, str):
        return None

    cleaned = _clean_text(text)
    cleaned_ocr = _clean_text(ocr_text) if ocr_text else ""
    # Combined text for instrument matching
    inst_search_text = f"{cleaned_ocr} {cleaned}".strip() if cleaned_ocr else cleaned

    if len(cleaned) < 3 and len(inst_search_text) < 5:
        return None

    # Step 1: Detect Instrument & Strike
    underlying = None
    strike = None
    option_type = None
    instrument = None

    inst_match = RE_INSTRUMENT.search(inst_search_text)
    if inst_match:
        raw_underlying, raw_strike, raw_type = inst_match.groups()
        strike = int(raw_strike)
        option_type = "CE" if raw_type.upper() in ("CE", "CALL") else "PE"
        if raw_underlying:
            underlying = re.sub(r'[\s_]|50', '', raw_underlying.upper())
        else:
            underlying = infer_underlying(strike)
        instrument = f"{underlying} {strike} {option_type}"
    else:
        alt_match = RE_INSTRUMENT_ALT.search(inst_search_text)
        if alt_match:
            raw_strike, raw_type, raw_underlying = alt_match.groups()
            strike = int(raw_strike)
            option_type = "CE" if raw_type.upper() in ("CE", "CALL") else "PE"
            if raw_underlying:
                underlying = re.sub(r'[\s_]|50', '', raw_underlying.upper())
            else:
                underlying = infer_underlying(strike)
            instrument = f"{underlying} {strike} {option_type}"

    # Step 2: Detect Action (Target Hit, SL Hit, or Entry)
    sl_match = RE_SL_HIT.search(cleaned)
    tgt_match = RE_TARGET_HIT.search(cleaned)
    entry_action_match = RE_ENTRY_ACTION.search(cleaned)

    # Check for SL Hit
    if sl_match:
        exit_p = 0.0
        exit_match = RE_EXIT_PRICE.search(cleaned)
        if exit_match:
            for g in exit_match.groups():
                if g:
                    try:
                        exit_p = float(g)
                        break
                    except ValueError:
                        continue

        return NormalizedSignal(
            raw_text=text,
            action="SL_HIT",
            underlying=underlying,
            strike=strike,
            option_type=option_type,
            instrument=instrument,
            exit_price=exit_p,
            confidence=0.95 if instrument else 0.80
        )

    # Check for Target Hit / Profit Booking
    if tgt_match:
        exit_p = 0.0
        exit_match = RE_EXIT_PRICE.search(cleaned)
        if exit_match:
            for g in exit_match.groups():
                if g:
                    try:
                        exit_p = float(g)
                        break
                    except ValueError:
                        continue

        # Try to extract target tier (T1, T2, etc.)
        tier = 1  # Default to Target 1
        if "SECOND" in cleaned.upper() or "2ND" in cleaned.upper() or "T2" in cleaned.upper():
            tier = 2
        elif "THIRD" in cleaned.upper() or "3RD" in cleaned.upper() or "T3" in cleaned.upper():
            tier = 3
        else:
            for g in tgt_match.groups():
                if g and g.isdigit():
                    tier = int(g)
                    break

        return NormalizedSignal(
            raw_text=text,
            action="TARGET_HIT",
            underlying=underlying,
            strike=strike,
            option_type=option_type,
            instrument=instrument,
            exit_price=exit_p,
            target_tier=tier,
            confidence=0.95 if instrument else 0.80
        )

    # Step 3: Check for Trade Entry
    # Valid entry requires an instrument (e.g. BANKNIFTY 48000 CE)
    if not instrument:
        return None

    # Check if entry action or prices are present
    entry_val = 0.0
    stop_loss_val = 0.0
    targets_list = []

    # Check entry range first (e.g., 200-210) -> use midpoint or upper bound
    range_match = RE_ENTRY_RANGE.search(cleaned)
    if range_match and ("BUY" in cleaned.upper() or "ABOVE" in cleaned.upper()):
        try:
            p1 = float(range_match.group(1))
            p2 = float(range_match.group(2))
            entry_val = p2  # Conservative entry at range high
        except ValueError:
            pass

    if entry_val == 0.0:
        ep_match = RE_ENTRY_PRICE.search(cleaned)
        if ep_match:
            try:
                entry_val = float(ep_match.group(1))
            except ValueError:
                entry_val = 0.0

    # Stop-Loss search
    sl_extracted = RE_STOP_LOSS.search(cleaned)
    if sl_extracted:
        try:
            stop_loss_val = float(sl_extracted.group(1))
        except ValueError:
            stop_loss_val = 0.0

    # Targets search
    tiered_matches = RE_TIERED_TARGETS.findall(cleaned)
    if tiered_matches:
        for t_str in tiered_matches:
            try:
                t_val = float(t_str)
                if t_val > 0 and t_val not in targets_list:
                    targets_list.append(t_val)
            except ValueError:
                continue
        targets_list.sort()

    if not targets_list:
        tgt_extracted = RE_TARGET_KEYWORD.search(cleaned)
        if tgt_extracted:
            targets_list = parse_targets(tgt_extracted.group(1), entry_price=entry_val)

    # Fallback: Check if there's any implicit target if not found via keyword
    if not targets_list and "/" in cleaned:
        slash_match = re.search(r"(\d{1,5}(?:\s*/\s*\d{1,5})+)", cleaned)
        if slash_match:
            targets_list = parse_targets(slash_match.group(1), entry_price=entry_val)

    # Validate that we have a realistic trade entry with an actual price
    if entry_val > 0.0:
        # Default safety: if stop_loss is 0, estimate 20% trailing risk
        if stop_loss_val == 0.0 and entry_val > 0:
            stop_loss_val = round(entry_val * 0.80, 2)

        # If targets list is empty, default 1:1.5 and 1:2 R:R targets
        if not targets_list and entry_val > 0 and stop_loss_val > 0:
            risk = max(1.0, entry_val - stop_loss_val)
            targets_list = [round(entry_val + (risk * 1.5), 2), round(entry_val + (risk * 2.5), 2)]

        return NormalizedSignal(
            raw_text=text,
            action="ENTRY",
            underlying=underlying,
            strike=strike,
            option_type=option_type,
            instrument=instrument,
            entry_price=entry_val,
            stop_loss=stop_loss_val,
            targets=targets_list,
            confidence=0.98 if entry_val > 0 else 0.85
        )

    return None
