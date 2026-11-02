import argparse, hashlib, importlib.metadata, json, platform
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from .data import fetch
from .features import dataset, partition
from .models import candidates, walk_forward
from .evaluation import scores, qlike, block_interval

def save(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+"\n")

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_digest():
    h=hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob("*.py")):
        h.update(p.name.encode());h.update(p.read_bytes())
    return h.hexdigest()

def run(stage, config, data_dir, out):
    c=json.loads(Path(config).read_text()); out=Path(out);out.mkdir(parents=True,exist_ok=True)
    frames={};returns={};provenance=[]
    for symbol in c["symbols"]:
        p,meta=fetch(symbol,c["start"],c["end"],data_dir)
        returns[symbol],frames[symbol]=dataset(p,c["horizon"]);provenance.append(meta)
    identity=dict(config_sha256=digest(config),data_sha256=[m["sha256"] for m in provenance],source_sha256=source_digest())
    if stage=="validate":
        trials=[]
        for cfg in candidates(c):
            by_symbol={};failures={};fits={}
            for symbol in c["symbols"]:
                _,valid,_=partition(frames[symbol],c["validation_start"],c["test_start"])
                pred,fail,fit=walk_forward(returns[symbol],frames[symbol],valid.index,cfg,c)
                by_symbol[symbol]=scores(valid.target.values,pred) if np.isfinite(pred).all() else None
                failures[symbol]=fail;fits[symbol]=fit
            eligible=all(x is not None for x in by_symbol.values())
            score=float(np.mean([v["qlike"] for v in by_symbol.values()])) if eligible else None
            trials.append(dict(configuration=cfg,validation_qlike=score,by_symbol=by_symbol,failures=failures,fits=fits))
            print(cfg,score,flush=True)
        winners={}
        for model in ("historical","ewma","garch","ridge"):
            valid=[t for t in trials if t["configuration"]["model"]==model and t["validation_qlike"] is not None]
            if not valid: raise RuntimeError(f"No valid {model} configuration; inspect trials")
            winners[model]=min(valid,key=lambda x:x["validation_qlike"])["configuration"]
        save(out/"validation.json",dict(identity=identity,trials=trials))
        save(out/"frozen.json",dict(identity=identity,selected=winners,selection="Equal ETF mean validation QLIKE; no test metrics accessed",frozen_utc=datetime.now(timezone.utc).isoformat()))
        print("Selection frozen. Run test separately.")
        return
    frozen=json.loads((out/"frozen.json").read_text())
    if frozen["identity"]!=identity: raise RuntimeError("Config, data or model source changed since selection")
    if (out/"test.json").exists(): raise RuntimeError("Test already evaluated; use a new output directory for an explicitly labeled rerun")
    all_rows=[];audit={};counts={}
    for symbol in c["symbols"]:
        train,valid,test=partition(frames[symbol],c["validation_start"],c["test_start"])
        counts[symbol]={name:dict(n=len(f),first=str(f.index[0].date()),last=str(f.index[-1].date()),last_label=str(f.label_end.max().date())) for name,f in [("train",train),("validation",valid),("test",test)]}
        for model,cfg in frozen["selected"].items():
            pred,fail,fit=walk_forward(returns[symbol],frames[symbol],test.index,cfg,c)
            audit[f"{symbol}/{model}"]=dict(failures=fail,fits=fit)
            if not np.isfinite(pred).all():
                save(out/"test-failure.json",audit)
                raise RuntimeError("Test forecast failure; inspect audit, do not silently drop observations")
            for t,y,p in zip(test.index,test.target,pred):
                all_rows.append(dict(date=str(t.date()),symbol=symbol,model=model,target=float(y),forecast=float(p),qlike=float(qlike(y,p)),squared_error=float((y-p)**2)))
    df=pd.DataFrame(all_rows); df.to_csv(out/"forecasts.csv",index=False)
    metrics=[]
    for (symbol,model),g in df.groupby(["symbol","model"]):
        metrics.append(dict(symbol=symbol,model=model,n=len(g),**scores(g.target.values,g.forecast.values)))
    # Equal-weight cross-ETF date loss; resample synchronized blocks to preserve dependence.
    losses=df.pivot_table(index="date",columns="model",values="qlike",aggfunc="mean")
    intervals=[]
    for model in frozen["selected"]:
        delta=losses[model]-losses["historical"]
        intervals.append(dict(model=model,mean_delta=float(delta.mean()),intervals={str(b):block_interval(delta.values,b,c["bootstrap_repetitions"],c["seed"]) for b in c["bootstrap_blocks"]}))
    packages={p:importlib.metadata.version(p) for p in ["numpy","pandas","scipy","scikit-learn","arch","matplotlib","exchange-calendars"]}
    save(out/"test.json",dict(identity=identity,generated_utc=datetime.now(timezone.utc).isoformat(),python=platform.python_version(),packages=packages,provenance=provenance,partitions=counts,metrics=metrics,paired_intervals=intervals,audit=audit,frozen_sha256=digest(out/"frozen.json")))
    print(json.dumps(metrics,indent=2))

def main():
    parser=argparse.ArgumentParser(description="VolatilityLab: freeze on validation, then evaluate final test")
    parser.add_argument("stage",choices=["validate","test","report"])
    parser.add_argument("--config",default="configs/study.json")
    parser.add_argument("--data-dir",default="data/raw")
    parser.add_argument("--out",default="docs/results")
    a=parser.parse_args()
    if a.stage=="report":
        from .reporting import render
        render(a.out)
    else: run(a.stage,a.config,a.data_dir,a.out)

if __name__=="__main__": main()
