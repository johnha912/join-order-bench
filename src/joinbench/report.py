"""One static HTML page (docs/index.html) with interactive Plotly charts.

Static on purpose: it opens from disk and hosts on GitHub Pages, no server.
Gray = any join order; blue / orange / aqua = the DP pick, the engine's own
optimizer, and plain left-to-right. Each also has its own marker shape.
"""

import csv
import html
import statistics
from collections import defaultdict

import plotly.graph_objects as go
from plotly.subplots import make_subplots

GRAY, MUTED, GRID = "#c3c2b7", "#898781", "#e1e0d9"
PICKS = [  # (column or plan name, legend label, color, marker symbol)
    ("is_dp", "DP pick", "#2a78d6", "star"),
    ("engine optimizer", "Engine optimizer", "#eb6834", "diamond"),
    ("is_left_to_right", "Left-to-right", "#1baf7a", "x"),
]


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            if k.startswith("is_"):
                r[k] = v == "True"
            elif k in ("seconds", "model_cost", "estimated", "actual", "rows"):
                r[k] = float(v) if v else None
    return rows


def picked(r, key):
    return r["plan"] == key if key == "engine optimizer" else r[key]


def ms(s):
    return f"{s * 1000:,.1f}"


def kpi_table(plans):
    groups = defaultdict(list)
    for r in plans:
        groups[r["engine"], r["chain"]].append(r)
    head = ("Engine", "Chain", "Join orders", "Result rows", "Best ms",
            "DP", "Engine optimizer", "Left-to-right", "Worst")
    body = []
    for (engine, chain), rs in groups.items():
        forced = [r for r in rs if r["plan"] != "engine optimizer"]
        t = {label: next(r["seconds"] for r in rs if picked(r, key)) for key, label, _, _ in PICKS}
        best = min(r["seconds"] for r in forced)
        worst = max(r["seconds"] for r in forced)
        cells = (engine, chain, len(forced), f"{rs[0]['rows']:,.0f}", ms(best),
                 *(f"{s / best:,.2f}×" for s in (*t.values(), worst)))
        body.append("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in cells) + "</tr>")
    th = "".join(f"<th>{h}</th>" for h in head)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def style(fig, height):
    fig.update_layout(
        height=height, margin=dict(l=60, r=20, t=50, b=50),
        font=dict(family="system-ui, Segoe UI, sans-serif"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.08, x=0), hoverlabel=dict(font_size=13),
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=GRAY, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, linecolor=GRAY, zeroline=False)
    return fig


def spread_figure(plans):
    """Every join order of every chain, one dot each, highlighted picks on top."""
    engines = list(dict.fromkeys(r["engine"] for r in plans))
    fig = make_subplots(rows=len(engines), cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=engines)
    for row, engine in enumerate(engines, 1):
        rs = [r for r in plans if r["engine"] == engine]
        forced = [r for r in rs if r["plan"] != "engine optimizer"]
        fig.add_trace(go.Box(
            x=[r["chain"] for r in forced], y=[r["seconds"] * 1000 for r in forced],
            text=[r["plan"] for r in forced], boxpoints="all", jitter=0.6, pointpos=0,
            fillcolor="rgba(0,0,0,0)", line=dict(width=0), marker=dict(color=GRAY, size=8),
            name="Any join order", legendgroup="all", showlegend=row == 1,
            hovertemplate="%{text}<br>%{y:,.1f} ms<extra></extra>",
        ), row=row, col=1)
        for key, name, color, symbol in PICKS:
            hit = [r for r in rs if picked(r, key)]
            fig.add_trace(go.Scatter(
                x=[r["chain"] for r in hit], y=[r["seconds"] * 1000 for r in hit],
                text=[r["plan"] for r in hit], mode="markers", name=name, legendgroup=name,
                showlegend=row == 1, marker=dict(color=color, symbol=symbol, size=14,
                                                 line=dict(color="white", width=2)),
                hovertemplate=f"{name}<br>%{{text}}<br>%{{y:,.1f}} ms<extra></extra>",
            ), row=row, col=1)
        fig.update_yaxes(type="log", title_text="ms (log)", row=row, col=1)
    return style(fig, 380 * len(engines))


def model_figure(plans):
    """Does a lower model cost actually mean a faster query? One panel per chain x engine."""
    engines = list(dict.fromkeys(r["engine"] for r in plans))
    chains = list(dict.fromkeys(r["chain"] for r in plans))
    cells = {(e, c): [r for r in plans if r["engine"] == e and r["chain"] == c
                      and r["plan"] != "engine optimizer"] for e in engines for c in chains}
    titles = []
    for e in engines:
        for c in chains:
            rs = cells[e, c]
            rho = statistics.correlation([r["model_cost"] for r in rs], [r["seconds"] for r in rs],
                                         method="ranked")
            titles.append(f"{e} · {c}<br>Spearman ρ = {rho:.2f}")
    fig = make_subplots(rows=len(engines), cols=len(chains), subplot_titles=titles,
                        horizontal_spacing=0.05, vertical_spacing=0.18)
    for row, e in enumerate(engines, 1):
        for col, c in enumerate(chains, 1):
            rs = cells[e, c]
            layers = ((False, "Any join order", GRAY, 8), (True, "DP pick", PICKS[0][2], 14))
            for flag, name, color, size in layers:
                pts = [r for r in rs if r["is_dp"] == flag]
                fig.add_trace(go.Scatter(
                    x=[r["model_cost"] for r in pts], y=[r["seconds"] * 1000 for r in pts],
                    text=[r["plan"] for r in pts], mode="markers", name=name, legendgroup=name,
                    showlegend=row == col == 1,
                    marker=dict(color=color, size=size, symbol="star" if flag else "circle",
                                line=dict(color="white", width=2 if flag else 0)),
                    hovertemplate="%{text}<br>model cost %{x:,.0f}<br>%{y:,.1f} ms<extra></extra>",
                ), row=row, col=col)
    fig.update_xaxes(type="log", title_text="model cost (rows, log)")
    fig.update_yaxes(type="log")
    fig.update_yaxes(title_text="ms (log)", col=1)
    fig.update_annotations(font_size=12)
    style(fig, 340 * len(engines) + 100)
    fig.update_layout(margin_t=110, legend_y=0.99, legend_yanchor="top", legend_yref="container")
    return fig


def cardinality_figure(cards):
    """The cost model's row estimate for every sub-chain, against the true count."""
    xs = [max(r["actual"], 1) for r in cards]
    ys = [max(r["estimated"], 1) for r in cards]
    lo, hi = min(xs + ys), max(xs + ys)
    fig = go.Figure([
        go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", line=dict(color=MUTED, width=1),
                   name="Perfect estimate", hoverinfo="skip"),
        go.Scatter(
            x=xs, y=ys, mode="markers", name="Sub-chain",
            marker=dict(color=PICKS[0][2], size=9, line=dict(color="white", width=1)),
            text=[f"{r['chain']}<br>{r['span']}" for r in cards],
            hovertemplate="%{text}<br>actual %{x:,.0f}<br>estimated %{y:,.0f}<extra></extra>",
        ),
    ])
    fig.update_xaxes(type="log", title_text="actual rows (log)")
    fig.update_yaxes(type="log", title_text="estimated rows (log)")
    return style(fig, 460)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Join Order Bench</title>
<style>
:root {{ color-scheme:light; --bg:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e;
  --line:#e1e0d9; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.5 system-ui,"Segoe UI",sans-serif; }}
main {{ max-width:1200px; margin:0 auto; padding:32px 16px; }}
h1 {{ margin:0 0 4px; font-size:28px; }} h2 {{ margin:40px 0 4px; font-size:20px; }}
p {{ color:var(--ink2); max-width:75ch; margin:4px 0 12px; }}
section {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:16px; }}
.scroll {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-size:14px; font-variant-numeric:tabular-nums; }}
th, td {{ padding:6px 10px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }}
th:nth-child(-n+2), td:nth-child(-n+2) {{ text-align:left; }}
th {{ color:var(--ink2); font-weight:600; }}
a {{ color:#2a78d6; }}
</style></head><body><main>
<h1>Join Order Bench</h1>
<p>v2 by Nguyen Ha, solo ·
<a href="https://github.com/johnha912/join-order-bench">source on GitHub</a></p>
<p>TPC-H {sf}. For each chain query, every possible join order is forced and timed on {engines},
then compared with the order a textbook dynamic program picks from single-table row counts,
and with the engine's own optimizer. Median of repeated runs, warm cache.</p>

<h2>Summary</h2>
<p>Each planner's runtime as a multiple of the fastest join order found by brute force.
1.00× is perfect.</p>
<section class="scroll">{table}</section>

<h2>Every join order, measured</h2>
<p>One gray dot per join order. A chain of n tables has Catalan(n−1) orders: 42 for six tables.</p>
<section>{spread}</section>

<h2>Does the cost model predict runtime?</h2>
<p>Model cost is the sum of intermediate row counts the DP minimizes. Spearman ρ near 1 means
the model ranks join orders the way the stopwatch does.</p>
<section>{model}</section>

<h2>Row estimates vs reality</h2>
<p>The model multiplies single-table counts by 1/|parent| per foreign key, assuming independent
filters. Points off the diagonal are where that assumption breaks.</p>
<section>{cards}</section>
</main>
</body></html>
"""


def build(plans_csv, cards_csv, out):
    plans, cards = load(plans_csv), load(cards_csv)
    config = {"responsive": True, "displaylogo": False}
    figs = [spread_figure(plans), model_figure(plans), cardinality_figure(cards)]
    parts = [f.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False, config=config)
             for i, f in enumerate(figs)]
    engines = " and ".join(dict.fromkeys(r["engine"] for r in plans))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PAGE.format(sf=f"SF {float(plans[0]['sf']):g}", engines=engines, table=kpi_table(plans),
                               spread=parts[0], model=parts[1], cards=parts[2]), encoding="utf-8")
