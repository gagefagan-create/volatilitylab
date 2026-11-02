"""Offline tests. All inputs here are synthetic, not market observations."""
import numpy as np
import pandas as pd
import pytest
from volatilitylab.features import dataset, observable, partition
from volatilitylab.evaluation import qlike, scores, block_interval
from volatilitylab.models import walk_forward

def fixture():
    p=pd.read_csv("tests/fixtures/synthetic_prices.csv",index_col=0,parse_dates=True).price
    return dataset(p)

def test_target_alignment():
    r,f=fixture()
    for t in f.index[::17]:
        i=r.index.get_loc(t)
        assert f.loc[t,"target"]==pytest.approx(np.square(r.iloc[i+1:i+6]).sum())
        assert f.loc[t,"label_end"]==r.index[i+5]

def test_purged_boundaries_and_observability():
    r,f=fixture(); a,b,c=partition(f,"2020-07-01","2020-10-01")
    assert a.label_end.max()<b.index.min()
    assert b.label_end.max()<c.index.min()
    known=observable(f,c.index[0]); assert (known.label_end<=c.index[0]).all()
    assert (known.index<c.index[0]).all()

def test_future_perturbation_cannot_change_forecast():
    r,f=fixture(); t=f.index[-40]
    changed=r.copy();changed.loc[changed.index>t]=5
    p=(100*np.exp(changed.fillna(0).cumsum()))
    rr,ff=dataset(p)
    cfg=dict(model="ridge",alpha=10,features="full")
    study=dict(horizon=5,refit_every=21,garch_window=1000)
    first=walk_forward(r,f,[t],cfg,study)[0]
    second=walk_forward(rr,ff,[t],cfg,study)[0]
    np.testing.assert_allclose(first,second,rtol=1e-8)

def test_metrics():
    assert qlike(2.,2.)==0
    assert qlike(2.,1.)==pytest.approx(1-np.log(2))
    assert scores(np.array([1.,3.]),np.array([2.,2.]))["mse"]==1
    with pytest.raises(ValueError): qlike(1,0)

def test_bootstrap_seed_and_dependence():
    x=np.repeat(np.arange(20.),5)
    assert block_interval(x,5,200,9)==block_interval(x,5,200,9)
    assert block_interval(x,5,200,9)!=block_interval(x,20,200,9)

def test_missing_prices_not_filled():
    r,f=fixture();p=100*np.exp(r.fillna(0).cumsum());p.iloc[100]=np.nan
    rr,ff=dataset(p)
    assert np.isnan(rr.iloc[100]) and np.isnan(rr.iloc[101])
    assert p.index[100] not in ff.index

def test_positive_baselines_and_reproducible_models():
    r,f=fixture(); origins=f.index[-15:]
    for cfg in [dict(model="historical",window=21),dict(model="ewma",decay=.94),dict(model="ridge",alpha=10,features="full"),dict(model="garch",distribution="normal")]:
        study=dict(horizon=5,refit_every=21,garch_window=200)
        a,fail,_=walk_forward(r,f,origins,cfg,study)
        b,_,_=walk_forward(r,f,origins,cfg,study)
        assert np.isfinite(a).all(),fail
        assert (a>0).all(); np.testing.assert_array_equal(a,b)

def test_calendar_holiday_bounds_and_missing_session_audit(tmp_path):
    """Synthetic Yahoo-shaped cache; no provider data and no network calls."""
    import json
    from volatilitylab.data import fetch
    dates=pd.to_datetime(['2010-01-04 21:00Z','2010-01-05 21:00Z','2010-01-07 21:00Z','2010-01-08 21:00Z'])
    obj={'chart':{'result':[{'timestamp':[int(t.timestamp()) for t in dates], 'indicators':{'adjclose':[{'adjclose':[100,101,102,103]}]}}]}}
    (tmp_path/'SYNTHETIC.json').write_text(json.dumps(obj))
    prices,meta=fetch('SYNTHETIC','2010-01-01','2010-01-08',tmp_path)
    assert len(prices)==5
    assert meta['missing_sessions']==['2010-01-06']
    assert np.isnan(prices.loc['2010-01-06'])
    assert meta['retrieved_utc']=='unknown cached retrieval'

def test_refit_audit_only_observable_labels():
    r,f=fixture();origins=f.index[-45:]
    _,_,fits=walk_forward(r,f,origins,dict(model='ridge',alpha=10,features='full'),dict(horizon=5,refit_every=21))
    assert len(fits)==3
    for fit in fits:
        assert pd.Timestamp(fit['last_label'])<=pd.Timestamp(fit['origin'])
