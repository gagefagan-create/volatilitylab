"""All features include information through close t only."""
import numpy as np
import pandas as pd

def dataset(prices, horizon=5):
    r = np.log(prices).diff()  # no filling: gaps invalidate adjacent returns
    sq = r*r
    x = pd.DataFrame(index=r.index)
    for w in (5,21,63): x[f"rv{w}"] = sq.rolling(w).mean()
    x["return1"] = r
    x["return5"] = r.rolling(5).sum()
    x["negative1"] = np.minimum(r, 0)
    x["target"] = sum(sq.shift(-j) for j in range(1,horizon+1))
    x["label_end"] = pd.Series(r.index, index=r.index).shift(-horizon)
    return r, x.dropna()

def partition(frame, validation_start, test_start):
    # No training/validation target contains returns from the next period.
    train = frame[(frame.index < validation_start) & (frame.label_end < validation_start)]
    validation = frame[(frame.index >= validation_start) & (frame.index < test_start) & (frame.label_end < test_start)]
    test = frame[frame.index >= test_start]
    return train, validation, test

def observable(frame, origin):
    return frame[(frame.index < origin) & (frame.label_end <= origin)]
