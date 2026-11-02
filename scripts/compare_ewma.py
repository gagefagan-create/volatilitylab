"""Secondary descriptive comparison, using frozen forecasts only; no model retuning."""
import argparse, json
from pathlib import Path
import pandas as pd
from volatilitylab.evaluation import block_interval
p=argparse.ArgumentParser();p.add_argument('--out',default='docs/results');a=p.parse_args()
root=Path(a.out)
f=pd.read_csv(root/'forecasts.csv')
c=json.loads(Path('configs/study.json').read_text())
loss=f.pivot_table(index='date',columns='model',values='qlike',aggfunc='mean')
rows=[]
for model in ['historical','garch','ridge']:
    delta=loss[model]-loss.ewma
    rows.append(dict(model=model,reference='ewma',mean_delta=float(delta.mean()),intervals={str(b):block_interval(delta.values,b,c['bootstrap_repetitions'],c['seed']) for b in c['bootstrap_blocks']}))
(root/'ewma_comparisons.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
