"""Build a standalone report and buildless results explorer from recorded outputs."""
import html, json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def render(directory):
    directory=Path(directory); docs=directory.parent
    result=json.loads((directory/"test.json").read_text())
    validation=json.loads((directory/"validation.json").read_text())
    frozen=json.loads((directory/"frozen.json").read_text())
    forecasts=pd.read_csv(directory/"forecasts.csv")
    metrics=pd.DataFrame(result["metrics"])
    aggregate=metrics.groupby("model")[["qlike","mse"]].mean().sort_values("qlike")
    best=aggregate.index[0]
    palette={"historical":"#708191","ewma":"#d16a38","garch":"#187d73","ridge":"#6d63a8"}
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False,"svg.hashsalt":"volatilitylab"})
    fig,ax=plt.subplots(figsize=(9,4.2),layout="constrained")
    for i,(model,row) in enumerate(aggregate.iterrows()):
        ax.barh(model,row.qlike,color=palette[model])
        ax.text(row.qlike+.01,i,f"{row.qlike:.3f}",va="center")
    ax.invert_yaxis();ax.set_xlim(0,aggregate.qlike.max()*1.2)
    ax.set_xlabel("Mean QLIKE · equal ETF weight · lower is better")
    ax.set_title("Final test: five-session variance forecasts, 2021–2024",loc="left",pad=18)
    fig.savefig(docs/"comparison.svg",metadata={"Date":None});plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(10,8),layout="constrained",sharex=True)
    for ax,symbol in zip(axes,["SPY","QQQ","IWM"]):
        d=forecasts[(forecasts.symbol==symbol)&(forecasts.model==best)].copy()
        ax.plot(pd.to_datetime(d.date),np.sqrt(d.target/5*252)*100,label="Observed daily-return proxy",color="#aab2ba",lw=.8)
        ax.plot(pd.to_datetime(d.date),np.sqrt(d.forecast/5*252)*100,label=best,color=palette[best],lw=.9)
        ax.set_title(symbol,loc="left");ax.set_ylabel("Annualized σ (%)")
    axes[0].legend(frameon=False,ncol=2);fig.savefig(docs/"paths.svg",metadata={"Date":None});plt.close(fig)
    n=metrics.n.iloc[0]
    lines=["# VolatilityLab", "", "## Does complexity improve volatility forecasts?", "",
        f"On this selected three-ETF case study, **{best.upper()}** has the lowest equal-weight test QLIKE ({aggregate.loc[best,'qlike']:.4f}). This is a result for SPY, QQQ and IWM during 2021–2024, not a general ranking of model families.","",
        "![Final test comparison](comparison.svg)","", "## Design and estimand", "",
        "Forecasts are made after close t. The target is Y_t = Σ(j=1…5) r²_(t+j), with r_t = log(P_t/P_(t−1)). This is a five-session, zero-mean daily-return variance proxy, not intraday realized volatility or the sample variance of five returns. All forecasts use decimal-return squared units and predict that same sum. No annualization is applied for scoring. The time-series display alone uses 100 × sqrt(252 × variance / 5). The conditional mean is assumed zero; this approximation is material for interpretation.","",
        "The universe is deliberately selected: SPY (large US equities), QQQ (Nasdaq-100 equities), and IWM (small US equities). These are established, liquid ETFs with long available histories. Liquidity is a selection rationale, not a measured screen in this project. The three funds overlap and are correlated. This is not a survivorship-free market sample.","",
        "Initial estimation: 2010–2017 (after 63-session feature warmup). Validation origins: 2018–2020. Untouched final test origins: 2021–2024, ending five sessions before the last available price. Training and validation origins whose labels end in the next partition are purged. Features at t use returns through t only. Supervised fitting at t includes only labels ending at or before t; therefore recent five-session targets are excluded until observable.","",
        "This is an adaptive, expanding walk-forward protocol: prior test outcomes may enter later supervised fits once fully observed, but test losses never select parameters. Ridge is refit every 21 evaluation origins on all observable labels. GARCH is refit on the latest 1,000 returns every 21 origins and filtered through each current close between refits. Historical and EWMA update daily. Validation and test each start with a new fit. Preprocessing is fit inside each ridge fit, never on future features.","",
        "All 14 candidate configurations were specified before test scoring: historical windows 21/63/126, EWMA decays .94/.97/.99, normal/Student-t GARCH(1,1), and ridge penalties .1/10/1000 crossed with full/volatility-only features. One configuration per model family is selected by mean validation QLIKE across the three ETFs. No post-test model selection is performed. The frozen selection records source, config and raw-data hashes; test execution rejects mismatches and refuses to overwrite an existing test run.","",
        "## Models", "",
        "Historical: five times the rolling mean squared return. EWMA: five times the exponentially weighted second moment (adjust=False, initialized from the first return). GARCH: zero-mean GARCH(1,1) conditional variance, summed over five analytical horizons; fitted in percent returns then converted back by dividing by 10,000. Ridge: standardized 5/21/63-session mean squared returns, latest return, five-session cumulative return, and negative latest return; direct five-session variance regression in percent-squared units. The volatility-only ablation removes the three signed-return features. Ridge predictions below 1e−12 are floored, with every occurrence logged. GARCH failures never receive silent fallback forecasts.","",
        "## Final test results", "", "| ETF | Model | Origins | QLIKE ↓ | MSE ↓ |", "|---|---|---:|---:|---:|"]
    for row in result["metrics"]: lines.append(f"| {row['symbol']} | {row['model']} | {row['n']} | {row['qlike']:.6f} | {row['mse']:.6e} |")
    lines += ["", "Aggregate QLIKE: "+"; ".join(f"{m}: {r.qlike:.4f}" for m,r in aggregate.iterrows())+".","",
        "QLIKE is y/f − log(y/f) − 1; lower is better, and a perfect proxy forecast scores zero. It penalizes underprediction sharply. MSE is in decimal-return fourth-power units. Both metrics are averaged over identical forecast origins; failed candidates are ineligible during validation and final-test failures stop the run.","",
        "## Dependence-aware uncertainty", "",
        "The paired statistic is each model’s QLIKE minus the selected historical baseline’s QLIKE, first averaged across ETFs for each date. A synchronized circular moving-block bootstrap resamples dates in blocks, preserving ETF correlation and local serial dependence from overlapping five-session targets. We use 2,000 replicates, seed 1729, and 95% percentile intervals at block lengths 5, 20 and 60. Negative deltas favor the model. These are descriptive, unadjusted intervals conditional on validation selection; they are not a multiple-testing-corrected discovery claim, and block length is a sensitivity assumption.","",
        "| Model | Mean Δ QLIKE | Block 5 CI | Block 20 CI | Block 60 CI |", "|---|---:|---|---|---|"]
    for row in result["paired_intervals"]:
        cells=[f"[{v[0]:.4f}, {v[1]:.4f}]" for v in row["intervals"].values()]
        lines.append(f"| {row['model']} | {row['mean_delta']:.4f} | "+" | ".join(cells)+" |")
    lines += ["", "## Sensitivity, ablations and failures", "", "These are validation results. All tested configurations, fit parameters, fit warnings and failure events are in [validation.json](results/validation.json). Final-test fitting audit is in [test.json](results/test.json).", "", "| Configuration | Validation QLIKE | Events |", "|---|---:|---:|"]
    for trial in validation["trials"]:
        score=trial["validation_qlike"]
        lines.append(f"| `{json.dumps(trial['configuration'],sort_keys=True)}` | {score if score is not None else 'FAILED'} | {sum(len(v) for v in trial['failures'].values())} |")
    events=sum(len(x["failures"]) for x in result["audit"].values())
    lines += ["",f"Final-test logged failure/floor events: **{events}**. The full event records distinguish clipping from actual failed forecasts. All successful fits and any optimizer warnings are retained. No unreported candidate search was performed. Block-length sensitivity is reported above; feature ablation and penalty/decay/window sensitivity are reported in the validation table. GARCH window length and refit cadence are fixed design choices, not tuned dimensions.","",
        "![Observed proxy and best aggregate model](paths.svg)","", "## Data provenance and usage", "",
        "Daily adjusted close comes from the publicly reachable Yahoo Finance chart endpoint. Yahoo defines adjusted close as accounting for splits and distributions ([provider explanation](https://in.help.yahoo.com/kb/adjusted-close-sln28256.html)). Retrieval uses adjclose explicitly, not an ambiguous Close column. These are retrospectively adjusted histories, not point-in-time vendor vintages; provider revisions and back adjustments may change future reruns. Constant historical rescaling cancels in adjacent log returns except for rounding. No claim of a fully point-in-time corporate-action dataset is made.","",
        "XNYS expected sessions provide the missing-observation audit. Prices are reindexed to those sessions; gaps are never forward-filled. Missing prices invalidate adjacent returns, feature windows and targets; incomplete rows are excluded before splitting. Nonpositive prices, duplicate dates and out-of-order observations cause errors. Weekends and exchange holidays are not missing observations.","",
        "| ETF | Retrieved UTC | First / last price | Observed | Missing XNYS sessions | Raw SHA-256 |", "|---|---|---|---:|---:|---|"]
    for p in result["provenance"]: lines.append(f"| {p['symbol']} | {p['retrieved_utc']} | {p['first']} / {p['last']} | {p['observed']} | {len(p['missing_sessions'])} | `{p['sha256']}` |")
    lines += ["", "Source request URLs and any missing dates appear in test.json. Public access does not imply permission to redistribute market data. Yahoo and upstream providers retain their rights; consult [Yahoo terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html) and applicable finance/data terms before use. No raw price histories are distributed in this repository. MIT covers the code, not market data. The published research includes derived forecasts and loss values for transparency, not a substitute price feed.","",
        "## Reproduction", "", "Run from the repository root with Python 3.14 (the recorded environment):", "", "```bash", "python3 -m venv .venv", "source .venv/bin/activate", "pip install -r requirements-lock.txt", "pip install --no-deps -e .", "pytest -q", "volatilitylab validate --out docs/reproduction", "volatilitylab test --out docs/reproduction", "volatilitylab report --out docs/reproduction", "python -m http.server 8000 --directory docs", "```", "",
        "The published directory docs/results is immutable evidence of this run; use a fresh output directory for reproduction. Downloaded inputs cache under ignored data/raw; keep the cache to reproduce exact prices. The registry lock pins the observed environment. The data provider may rate-limit or revise histories; failed downloads stop execution. Exact original data hashes can be checked, but byte-exact reruns require the original local cache because redistribution rights are not assumed. No network is used by the offline tests. All fixtures in tests/fixtures are explicitly synthetic.","",
        "## Limitations", "",
        "A single selected universe, one validation window and one test window cannot establish universal superiority. All ETFs share equity risk; there is no independent asset-class replication. Five daily returns form a noisy variance proxy and miss intraday price variation and microstructure effects. Retrospective adjustments, a small configuration grid, fixed refit frequency, bootstrap assumptions, and regime changes limit interpretation. Training outcomes enter the walk-forward model only after they become observable; this does not make vendor vintages point-in-time. Repeated future research on this test period would require a new holdout. Forecast accuracy is not tradable profitability: no strategy, execution costs, portfolio returns, recommendations or brokerage integration are evaluated.","",
        "## References and audit files", "",
        "[GARCH analytical forecasting documentation](https://arch.readthedocs.io/en/stable/univariate/forecasting.html) · [frozen selection](results/frozen.json) · [all validation configurations](results/validation.json) · [test provenance and fitting audit](results/test.json) · [per-origin forecasts and losses](results/forecasts.csv).", "",
        f"Implementation version 1.0.0. Python {result['python']}. Packages: {json.dumps(result['packages'],sort_keys=True)}. Source SHA-256: `{result['identity']['source_sha256']}`. Config SHA-256: `{result['identity']['config_sha256']}`. Selection frozen: {frozen['frozen_utc']}. Test generated: {result['generated_utc']}."]
    report="\n".join(lines)+"\n"
    (docs/"report.md").write_text(report)
    # Minimal markdown presentation with escaped content; no external JS dependency.
    import re
    def inline(s):
        s=html.escape(s)
        s=re.sub(r"!\[([^\]]*)\]\(([^)]+)\)",r'<img alt="\1" src="\2">',s)
        s=re.sub(r"\[([^\]]*)\]\(([^)]+)\)",r'<a href="\2">\1</a>',s)
        s=re.sub(r"\*\*([^*]+)\*\*",r'<strong>\1</strong>',s)
        s=re.sub(r"`([^`]+)`",r'<code>\1</code>',s)
        return s
    rendered=[];code=False;table=False
    for line in lines:
        if line.startswith("```"):
            rendered.append("</code></pre>" if code else "<pre><code>");code=not code;continue
        if code:rendered.append(html.escape(line)+"\n");continue
        if line.startswith("|"):
            if not table:rendered.append('<div class="table-wrap"><table>');table=True
            if re.match(r"\|[-: |]+\|$",line):continue
            rendered.append("<tr>"+"".join("<td>"+inline(c.strip())+"</td>" for c in line.strip("|").split("|"))+"</tr>");continue
        if table:rendered.append("</table></div>");table=False
        if line.startswith("## "):rendered.append("<h2>"+inline(line[3:])+"</h2>")
        elif line.startswith("# "):rendered.append("<h1>"+inline(line[2:])+"</h1>")
        elif line:rendered.append("<p>"+inline(line)+"</p>")
    (docs/"report.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VolatilityLab · Research report</title><link rel="stylesheet" href="style.css"><body><nav><a href="index.html">← Results explorer</a><a href="report.md">Markdown report</a></nav><main class="report">'+"\n".join(rendered)+"</main></body></html>")
    # Compact website data includes paths, outcomes, all selection scores and intervals.
    web=dict(metrics=result["metrics"],intervals=result["paired_intervals"],selected=frozen["selected"],trials=[{k:v for k,v in t.items() if k in ("configuration","validation_qlike")} for t in validation["trials"]],paths={})
    for symbol in ["SPY","QQQ","IWM"]:
        sub=forecasts[forecasts.symbol==symbol]
        pivot=sub.pivot(index="date",columns="model",values="forecast")
        actual=sub.groupby("date").target.first()
        web["paths"][symbol]=dict(dates=pivot.index.tolist(),target=actual.tolist(),forecasts={m:pivot[m].tolist() for m in pivot})
    (directory/"explorer.json").write_text(json.dumps(web,separators=(",",":"),allow_nan=False))
    readme=f"""# VolatilityLab

Independent, reproducible research on a concrete question: **Do more complex models improve out-of-sample volatility forecasts over historical and exponentially weighted baselines?**

[Interactive explorer](https://gagefagan-create.github.io/volatilitylab/) · [Full research report](https://gagefagan-create.github.io/volatilitylab/report.html) · [Report source](docs/report.md)

## Findings

On SPY, QQQ and IWM in the frozen 2021–2024 test, **{best.upper()}** has the lowest equal-weight QLIKE: **{aggregate.loc[best,'qlike']:.4f}**. This selected case study does not establish general model superiority. See the report for each ETF, MSE, paired block-bootstrap uncertainty, all 14 validation configurations, ablations and failure logs. Negative outcomes are retained.

![Final test comparison](docs/comparison.svg)

## Reproduce

Python 3.14 was used for the published run. From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
pip install --no-deps -e .
pytest -q
volatilitylab validate --out docs/reproduction
volatilitylab test --out docs/reproduction
volatilitylab report --out docs/reproduction
python -m http.server 8000 --directory docs
```

Open http://localhost:8000. Test execution requires a frozen validation record with matching config/data/source hashes and refuses to overwrite a test result. Keep `data/raw` locally for exact-input reproduction; Yahoo can revise historical data. A clean re-download may not match the published hashes. Offline tests use only clearly labeled synthetic fixtures.

## Architecture

- `data.py`: adjusted-close acquisition, calendar checks and raw input hashes.
- `features.py`: backward features, five-session targets and purged partitions.
- `models.py`: historical, EWMA, analytical GARCH and standardized ridge; observable-label walk-forward fitting.
- `evaluation.py`: QLIKE, MSE and synchronized moving-block intervals.
- `reporting.py`: plots, research report and buildless interactive explorer.
- `cli.py`: separate validation, frozen selection, final test and report commands.
- `configs/study.json`: complete pre-test search grid and deterministic seed.
- `docs/results`: actual forecasts, configuration selection, provenance and fit audits.

The daily-return variance proxy is the sum of the next five squared log returns, not intraday realized volatility. Evaluation uses chronological initial training (2010–2017), validation (2018–2020) and final testing (2021–2024). Preprocessing is refit only on observable training labels; forward targets crossing selection boundaries are purged. The final test is adaptive walk-forward, with prior outcomes entering subsequent fits once observed, while hyperparameters remain frozen.

## Data and limitations

SPY, QQQ and IWM are an explicitly selected correlated equity ETF case study, not a survivorship-free market sample. Yahoo adjusted close includes splits and distributions; prices are retrospectively adjusted and can be revised. The report records retrieval times, exact request URLs, missing expected sessions and SHA-256 hashes. Raw provider data is ignored and excluded from Git; MIT applies to code, not market data. Respect provider terms and usage restrictions.

This is forecast research, not an investment recommendation or evidence of tradable profitability. The small universe, one test window, noisy daily proxy, configuration selection and bootstrap assumptions limit generalization.

## Checks and publication

GitHub Actions runs the offline integrity suite on every push and PR. The Pages workflow deploys the committed `docs` artifact without fetching data or rerunning experiments. Repository Settings → Pages should use GitHub Actions. The explorer has no external JavaScript dependencies and runs entirely in the browser.
"""
    (docs.parent/"README.md").write_text(readme)
