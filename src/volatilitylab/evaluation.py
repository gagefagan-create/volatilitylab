import numpy as np

def qlike(y, forecast):
    y=np.asarray(y); forecast=np.asarray(forecast)
    if np.any(y<=0) or np.any(forecast<=0): raise ValueError("QLIKE requires positive values")
    ratio=y/forecast
    return ratio-np.log(ratio)-1

def scores(y, forecast):
    return dict(qlike=float(qlike(y,forecast).mean()),mse=float(np.mean((np.asarray(y)-forecast)**2)))

def block_interval(values, block=20, repetitions=2000, seed=1729):
    """Paired circular moving-block bootstrap percentile interval for mean loss delta."""
    x=np.asarray(values); rng=np.random.default_rng(seed); n=len(x)
    if n<block: raise ValueError("Series shorter than bootstrap block")
    starts=rng.integers(n,size=(repetitions,int(np.ceil(n/block))))
    indices=(starts[:,:,None]+np.arange(block))%n
    means=x[indices.reshape(repetitions,-1)[:,:n]].mean(axis=1)
    return [float(v) for v in np.quantile(means,[.025,.975])]
