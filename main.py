"""cbBTC dip-buy bot for make.fun btc-race-24h-20261123-0511.

Protocol: agent-fun/bars-replay/v1, newline-delimited JSON on stdin/stdout.
One reply per batch, echoing its seq. Pure standard library (json, sys only),
integer-only money math, fully deterministic.

Strategy (parameters derived from my own experiments on the new dev window,
1440 one-minute cbBTC bars, first close $58,956.59, last close $61,102.18):
the dev window trends up overall but is strongly mean-reverting at short
horizons: after a rise of 100+ bps over 30 bars the next 30 bars average
about -34 bps, while after a drop of 80+ bps over 10-15 bars the next
30 bars average about +26 to +30 bps with every sampled window positive.
So the bot buys sharp 15-bar dips with its full cash and rides the
bounce with a trailing stop, instead of chasing momentum.

  * Entry: close at least 55 bps below the close 15 bars earlier.
  * Size: 100% of cash on every entry (one open position at most).
  * Exit, whichever comes first:
      - take profit at +200 bps vs the position's average cost,
      - stop loss at -120 bps vs average cost,
      - trailing stop: once up at least +20 bps, sell if the price falls
        25 bps from the highest close seen since entry,
      - time stop: sell after holding 480 bars (8 hours).
  * Orders carry max_slippage_bps 300, far above the usual 1-minute move
    (max about 72 bps on the dev window) plus the 2 bps modelled slippage
    and roughly 17 bps of own price impact on a full-size buy, so fills
    are almost never rejected for slippage.
  * No trade is ever sent on a warm-up batch.
"""

import json
import sys

SYMBOL = "CBBTC"

# Entry: dip in bps vs the close DIP_WINDOW bars ago.
DIP_WINDOW = 15
DIP_BPS = 55

# Exits, all measured in bps against the position's average cost price.
TAKE_BPS = 200
STOP_BPS = 120
# Trailing stop: armed once the gain reaches TRAIL_MIN_GAIN_BPS, then a
# fall of TRAIL_BPS from the highest close since entry sells.
TRAIL_MIN_GAIN_BPS = 20
TRAIL_BPS = 25
# Time stop, in bars held.
MAX_HOLD_BARS = 480

MAX_SLIPPAGE_BPS = 300


def should_exit(gain_bps, trail_drop_bps, bars_held):
    """True when any exit rule fires: take profit, stop loss, time stop,
    or the trailing stop once it is armed by a large enough gain."""
    if gain_bps >= TAKE_BPS:
        return True
    if gain_bps <= -STOP_BPS:
        return True
    if bars_held >= MAX_HOLD_BARS:
        return True
    return gain_bps >= TRAIL_MIN_GAIN_BPS and trail_drop_bps >= TRAIL_BPS


def main():
    closes = []
    entry_seq = -1
    peak_px = 0
    warmup_bars = 0
    order_no = 0
    out = sys.stdout
    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        kind = msg.get("type")
        if kind == "hello":
            warmup_bars = msg.get("warmup_bars", 0) or 0
            continue
        if kind == "done":
            break
        if kind != "batch":
            continue
        seq = msg["seq"]
        bar = None
        for b in msg.get("bars") or []:
            if b.get("symbol") == SYMBOL:
                bar = b
                break
        account = msg.get("account") or {}
        cash = int(account.get("cash_quote_units", "0"))
        qty = 0
        cost = 0
        for p in account.get("positions") or []:
            if p.get("symbol") == SYMBOL:
                qty = int(p["qty"])
                cost = int(p["cost_quote_units"])
        orders = []
        if bar is not None:
            close = int(bar["c"])
            closes.append(close)
            if qty > 0:
                # Average cost price, in price units (scale 5):
                # value(qty, px) = qty * px // 10**7, so px = cost * 10**7 // qty.
                entry_px = cost * 10 ** 7 // qty
                if entry_seq < 0:
                    entry_seq = seq
                    peak_px = close
                if close > peak_px:
                    peak_px = close
                gain = (close - entry_px) * 10000 // entry_px
                trail_drop = (peak_px - close) * 10000 // peak_px
                if should_exit(gain, trail_drop, seq - entry_seq):
                    order_no += 1
                    orders.append({
                        "side": "sell",
                        "client_id": "s%d" % order_no,
                        "symbol": SYMBOL,
                        "qty": str(qty),
                        "max_slippage_bps": MAX_SLIPPAGE_BPS,
                    })
            else:
                entry_seq = -1
                peak_px = 0
                if seq >= warmup_bars and len(closes) > DIP_WINDOW:
                    ref = closes[-1 - DIP_WINDOW]
                    drop = (ref - close) * 10000 // ref
                    if drop >= DIP_BPS and cash >= 1000000:
                        order_no += 1
                        orders.append({
                            "side": "buy",
                            "client_id": "b%d" % order_no,
                            "symbol": SYMBOL,
                            "notional_quote_units": str(cash),
                            "max_slippage_bps": MAX_SLIPPAGE_BPS,
                        })
        out.write(json.dumps({"type": "reply", "seq": seq, "orders": orders},
                             separators=(",", ":")) + "\n")
        out.flush()


main()
