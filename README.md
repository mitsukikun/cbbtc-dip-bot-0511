[![make.fun · btc-race-24h-20261123-0511](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/mitsukikun/cbbtc-dip-bot-0511/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/mitsukikun/cbbtc-dip-bot-0511/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

# cbBTC Dip-Buy Bot — btc-race-24h-20261123-0511

A mean-reversion bot that trades Coinbase Wrapped BTC (cbBTC) against USDC
on 1-minute bars, speaking `agent-fun/bars-replay/v1` (NDJSON on stdin/stdout).
Pure Python 3.13 standard library (`json`, `sys` only), integer-only money
math, fully deterministic: two runs on the same data produce identical orders.

## Strategy

The dev window (1,440 bars, first close $58,956.59, last close $61,102.18)
trends up overall but is strongly mean-reverting at short horizons. Measured
on that window:

- After a rise of 100+ bps over 30 bars, the next 30 bars average about
  **-34 bps** — chasing momentum loses.
- After a drop of 80+ bps over 10–15 bars, the next 30 bars average about
  **+26 to +30 bps**, with every sampled window positive — dips bounce.

So the bot buys sharp dips with its full cash and rides the bounce with a
trailing stop instead of chasing momentum.

**Entry:** buy with 100% of cash when the close is at least **55 bps** below
the close **15 bars** earlier. At most one open position.

**Exit** (whichever comes first, all measured against the position's average
cost price):

- Take profit at **+200 bps**
- Stop loss at **-120 bps**
- Trailing stop: once the gain reaches **+20 bps**, sell if the price falls
  **25 bps** from the highest close since entry
- Time stop: sell after holding **480 bars** (8 hours)

Orders carry `max_slippage_bps` 300 — far above the dev window's largest
1-minute move (about 72 bps) plus the 2 bps modelled slippage and roughly
17 bps of own price impact on a full-size buy — so fills are almost never
rejected for slippage. No orders are sent on warm-up batches.

## Verified dev-window results

Graded with the official replay (`python3 replay_bars.py <kit> main.py`;
the `grade-local --driver process` path is Node-only and Docker is not
available in this environment, so the Python replay script supplied with
the kit was used). Two separate runs gave byte-identical results:

| Metric | Value |
|---|---|
| Net PnL | **+$37.06** (37,062,878 micro-USDC) |
| Final cash | $1,037.06 (from $1,000 start) |
| Trades (fills) | 11 |
| Fees paid | $4.94 |
| Max drawdown | **1.46%** (limit 25%) |
| Determinism | Two runs identical |

For reference, buy-and-hold on the same window gains about +$36.39 gross
(first to last close, +363 bps) before its round-trip costs; this bot beats
it while spending most of the window in cash and keeping drawdown under 1.5%.

Split-half robustness (each half restarted with $1,000): first 12 hours
+$32.65, second 12 hours +$3.16 — positive in both halves. Neighbouring
parameters (dip 45–70 bps, trailing stop 25–35 bps, hold 240–480 bars)
all stay profitable on the dev window, so the result is not a single
knife-edge parameter choice.

## Files

- `main.py` — the bot (entrypoint)
- `README.md` — this file
- `LICENSE` — MIT

## Running

The grader runs `python3 -P -s main.py`; the bot reads the hello, one batch
per minute, and `done` from stdin and writes exactly one `reply` per batch
to stdout, echoing its `seq`.
