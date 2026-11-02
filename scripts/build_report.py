"""Render the report plus secondary EWMA comparison without rerunning models."""
import argparse,json,subprocess,sys
from pathlib import Path
from volatilitylab.reporting import render
p=argparse.ArgumentParser();p.add_argument('--out',default='docs/results');a=p.parse_args()
root=Path(a.out);docs=root.parent
render(root)
subprocess.run([sys.executable,'scripts/compare_ewma.py','--out',str(root)],check=True)
rows=json.loads((root/'ewma_comparisons.json').read_text())
text='''## Comparison with the EWMA baseline

Complexity shows no clear improvement over EWMA in this case study. Ridge leads aggregate QLIKE by only 0.0000824, while EWMA has the lowest aggregate MSE. At block length 20, ridge minus EWMA QLIKE has a 95% interval of [−0.03185, 0.03147]; GARCH minus EWMA is [−0.02215, 0.02178]. Neither excludes zero at any of the three tested block lengths. These descriptive intervals do not prove equivalence or rule out useful gains elsewhere.

This secondary comparison was computed from the already frozen final-test forecasts to address both simple baselines. It introduced no new model configurations, refits, hyperparameter choices or test reruns. Code: scripts/compare_ewma.py. The primary source hash in frozen.json covers the package as evaluated; these reporting scripts are an additional transparent analysis of its outputs.

| Model | Mean Δ vs EWMA | Block 5 CI | Block 20 CI | Block 60 CI |
|---|---:|---|---|---|
'''
for row in rows:
    ci=['['+f'{v[0]:.5f}, {v[1]:.5f}'+']' for v in row['intervals'].values()]
    text+=f"| {row['model']} | {row['mean_delta']:.7f} | "+' | '.join(ci)+' |\n'
text+='\n[Machine-readable comparisons](results/ewma_comparisons.json). The same synchronized block-bootstrap procedure and seed apply.\n\n'
md=docs/'report.md';md.write_text(md.read_text().replace('## Dependence-aware uncertainty',text+'## Dependence-aware uncertainty').replace('volatilitylab report --out docs/reproduction','python scripts/build_report.py --out docs/reproduction'))
rows_html=''.join('<tr><td>'+r['model']+'</td><td>'+f"{r['mean_delta']:.7f}"+'</td>'+''.join('<td>'+f'[{v[0]:.5f}, {v[1]:.5f}]'+'</td>' for v in r['intervals'].values())+'</tr>' for r in rows)
section='<h2>Comparison with the EWMA baseline</h2><p>Complexity shows no clear improvement over EWMA in this case study. Ridge leads aggregate QLIKE by only 0.0000824; EWMA has the lowest aggregate MSE. Neither ridge nor GARCH has a paired interval against EWMA excluding zero at any tested block length. These descriptive intervals do not establish equivalence.</p><p>This secondary comparison uses the already frozen test forecasts. It adds no model configurations, retuning, refits or test reruns. The original package source hash remains unchanged; scripts/compare_ewma.py records this additional reporting analysis.</p><div class="table-wrap"><table><tr><th>Model</th><th>Mean Δ vs EWMA</th><th>Block 5 CI</th><th>Block 20 CI</th><th>Block 60 CI</th></tr>'+rows_html+'</table></div>'
h=docs/'report.html';h.write_text(h.read_text().replace('<h2>Dependence-aware uncertainty</h2>',section+'<h2>Dependence-aware uncertainty</h2>').replace('volatilitylab report --out docs/reproduction','python scripts/build_report.py --out docs/reproduction'))
web=json.loads((root/'explorer.json').read_text());web['intervals_ewma']=rows
(root/'explorer.json').write_text(json.dumps(web,separators=(',',':'),allow_nan=False))
r=docs.parent/'README.md';s=r.read_text();s=s.replace('![Final test comparison]', 'Ridge’s aggregate QLIKE lead over EWMA is only 0.0000824, with a 20-session block-bootstrap interval of [−0.03185, 0.03147]. GARCH also shows no clear gain over EWMA. EWMA has the lowest aggregate MSE. The evidence does not establish an advantage from model complexity.\n\n![Final test comparison]',1).replace('volatilitylab report --out docs/reproduction','python scripts/build_report.py --out docs/reproduction');r.write_text(s)
