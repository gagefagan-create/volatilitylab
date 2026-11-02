import warnings
import numpy as np
from arch import arch_model
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .features import observable

FLOOR = 1e-12

def candidates(c):
    return ([dict(model="historical",window=w) for w in c["historical_windows"]]
        + [dict(model="ewma",decay=d) for d in c["ewma_lambdas"]]
        + [dict(model="garch",distribution=d) for d in ("normal","t")]
        + [dict(model="ridge",alpha=a,features=f) for a in c["ridge_alphas"] for f in c["feature_sets"]])

def walk_forward(returns, frame, origins, cfg, study):
    predictions=[]; failures=[]; fits=[]; fitted=None; last=-10**9
    cols=[c for c in frame if c not in ("target","label_end")]
    if cfg.get("features")=="vol_only": cols=[c for c in cols if c.startswith("rv")]
    for i,t in enumerate(origins):
        history=returns.loc[:t].dropna()
        h=study["horizon"]
        try:
            if cfg["model"]=="historical": value=h*np.mean(np.square(history.iloc[-cfg["window"]:]))
            elif cfg["model"]=="ewma": value=h*history.pow(2).ewm(alpha=1-cfg["decay"],adjust=False).mean().iloc[-1]
            elif cfg["model"]=="ridge":
                if i-last>=study["refit_every"]:
                    known=observable(frame,t)
                    fitted=make_pipeline(StandardScaler(),Ridge(alpha=cfg["alpha"]))
                    # Fit variance levels in percent-squared units for conditioning.
                    fitted.fit(known[cols], known.target*10000)
                    fits.append(dict(origin=str(t.date()),last_label=str(known.label_end.max().date()),n=len(known)))
                    last=i
                value=fitted.predict(frame.loc[[t],cols])[0]/10000
            else:
                if i-last>=study["refit_every"]:
                    hist=history.iloc[-study["garch_window"]:]*100
                    with warnings.catch_warnings(record=True) as ws:
                        fitted=arch_model(hist,mean="Zero",vol="GARCH",p=1,q=1,dist=cfg["distribution"],rescale=False).fit(disp="off")
                    if fitted.convergence_flag: raise RuntimeError(f"GARCH convergence flag {fitted.convergence_flag}")
                    fits.append(dict(origin=str(t.date()),parameters=fitted.params.to_dict(),warnings=[str(w.message) for w in ws]))
                    last=i
                # Fixed parameters between refits; filter every return through current t.
                current=arch_model(history.iloc[-study["garch_window"]:]*100,mean="Zero",vol="GARCH",p=1,q=1,dist=cfg["distribution"],rescale=False).fix(fitted.params)
                value=current.forecast(horizon=h,reindex=False).variance.iloc[-1].sum()/10000
            if not np.isfinite(value): raise ValueError("Nonfinite prediction")
            if value<FLOOR: failures.append(dict(origin=str(t.date()),event="prediction floored",raw=float(value)))
            predictions.append(max(value,FLOOR))
        except Exception as e:
            failures.append(dict(origin=str(t.date()),event="failed",error=str(e)))
            predictions.append(float("nan"))  # never silently substitute a baseline
    return np.array(predictions), failures, fits
