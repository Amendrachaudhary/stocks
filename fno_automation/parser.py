import re

def parse_message(text):
    """
    Parses Yahoo Finance options market text to extract trade parameters.
    Returns a dictionary with parsed data or None if not a valid trade alert.
    """
    if not text:
        return None
        
    # Standardize spacing and newlines for easier regex matching
    text = text.replace('\n', ' ')
    
    # Try to extract the instrument first
    # e.g. "BANKNIFTY 48000 CE", "FIN NIFTY 21000 PE", "NIFTY 22000 CE"
    instrument_match = re.search(r"(BANK\s?NIFTY|NIFTY|FIN\s?NIFTY)\s?(\d{5})\s?(CE|PE)", text, re.IGNORECASE)
    
    instrument = None
    if instrument_match:
        index_name = instrument_match.group(1).upper().replace(' ', '')
        strike = instrument_match.group(2)
        option_type = instrument_match.group(3).upper()
        instrument = f"{index_name} {strike} {option_type}"
        
    # Detect Exits
    target_hit_match = re.search(r"(target hit|tgt hit|book profit)", text, re.IGNORECASE)
    sl_hit_match = re.search(r"(sl hit|stoploss hit)", text, re.IGNORECASE)
    
    if sl_hit_match and instrument:
        exit_price_match = re.search(r"(?:at|cmp|exit at)[\s:]*([\d\.]+)", text, re.IGNORECASE)
        exit_price = float(exit_price_match.group(1)) if exit_price_match else 0.0
        return {
            "action": "SL_HIT",
            "instrument": instrument,
            "exit_price": exit_price
        }
        
    if target_hit_match and instrument:
        exit_price_match = re.search(r"(?:at|cmp|exit at)[\s:]*([\d\.]+)", text, re.IGNORECASE)
        exit_price = float(exit_price_match.group(1)) if exit_price_match else 0.0
        return {
            "action": "TARGET_HIT",
            "instrument": instrument,
            "exit_price": exit_price
        }

    # Detect Entries
    entry_match = re.search(r"(buy|ce|pe)", text, re.IGNORECASE)
    if entry_match and instrument:
        entry_price_match = re.search(r"(?:above|entry|buy at|cmp)[\s:]*([\d\.]+)", text, re.IGNORECASE)
        sl_match = re.search(r"(?:sl|stoploss)[\s:]*([\d\.]+)", text, re.IGNORECASE)
        
        entry_price = float(entry_price_match.group(1)) if entry_price_match else 0.0
        stop_loss = float(sl_match.group(1)) if sl_match else 0.0
        
        targets_match = re.search(r"(?:target|tgt)[\s:]*([\d\. \-\|]+)", text, re.IGNORECASE)
        targets = targets_match.group(1).strip() if targets_match else ""
        
        if entry_price > 0:
            return {
                "action": "ENTRY",
                "instrument": instrument,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "targets": targets
            }
            
    return None

def calculate_pnl(instrument, entry_price, exit_price, action, config_lot_sizes):
    """
    Calculates points and rupees based on instrument type.
    """
    if entry_price <= 0:
        return 0.0, 0.0
        
    # Options buying logic: PNL is (exit - entry)
    # If exit price isn't provided or parsed, we assume 0 PnL or skip
    pnl_points = exit_price - entry_price if exit_price > 0 else 0.0
    
    # Extract base instrument (e.g., BANKNIFTY)
    base_instrument = instrument.split()[0].upper()
    lot_size = config_lot_sizes.get(base_instrument, 0)
    
    pnl_rupees = pnl_points * lot_size
    return pnl_points, pnl_rupees

def enrich_entry_data(parsed_data, config_lot_sizes):
    """
    Calculates capital required and potential gains.
    Returns the enriched data, or None if it exceeds max capital (10k).
    """
    if not parsed_data or parsed_data.get("action") != "ENTRY":
        return parsed_data
        
    instrument = parsed_data["instrument"]
    entry_price = parsed_data["entry_price"]
    
    base_instrument = instrument.split()[0].upper()
    lot_size = config_lot_sizes.get(base_instrument, 0)
    
    capital_required = entry_price * lot_size
    
    # 10k Filter Rule
    if capital_required > 10000:
        print(f"Trade filtered out: {instrument} requires Rs. {capital_required:.2f} which is > 10k")
        return None
        
    parsed_data["capital_required"] = f"Rs. {capital_required:.2f}"
    
    targets_str = parsed_data.get("targets", "")
    if targets_str:
        target_values = re.findall(r"[\d\.]+", targets_str)
        if target_values:
            gains = []
            for i, t in enumerate(target_values, 1):
                try:
                    t_val = float(t)
                    if t_val > entry_price:
                        gain = (t_val - entry_price) * lot_size
                        gains.append(f"T{i}: Rs. {gain:.2f}")
                except ValueError:
                    pass
            if gains:
                parsed_data["potential_gains"] = " | ".join(gains)
                
    return parsed_data
