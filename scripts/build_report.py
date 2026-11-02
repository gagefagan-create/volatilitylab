"""Render recorded forecasts plus a secondary EWMA comparison; never refit models."""
import argparse
import html
import json
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

import pandas as pd
from volatilitylab.reporting import render

parser = argparse.ArgumentParser()
parser.add_argument('--out', default='docs/results')
args = parser.parse_args()
root = Path(args.out)
docs = root.parent
project = Path(__file__).resolve().parents[1]
is_published = root.resolve() == project / 'docs/results'
if is_published:
    render(root)
else:
    # The frozen renderer assumes site/results and writes a README one level up.
    # Isolate those assumptions so fresh reproductions cannot overwrite published evidence.
    with tempfile.TemporaryDirectory(prefix='volatilitylab-report-') as temporary:
        sandbox = Path(temporary)
        site = sandbox / 'site'
        shutil.copytree(root, site / 'results')
        render(site / 'results')
        docs.mkdir(parents=True, exist_ok=True)
        for name in ('report.md', 'report.html', 'comparison.svg', 'paths.svg'):
            shutil.copy2(site / name, docs / name)
        shutil.copy2(site / 'results/explorer.json', root / 'explorer.json')
        shutil.copy2(sandbox / 'README.md', docs / 'README.md')
    for name in ('index.html', 'app.js', 'style.css'):
        contents = (project / 'docs' / name).read_text()
        if name in ('index.html', 'app.js'):
            contents = contents.replace('results/', root.name + '/')
        (docs / name).write_text(contents)
subprocess.run([sys.executable, 'scripts/compare_ewma.py', '--out', str(root)], check=True)
rows = json.loads((root / 'ewma_comparisons.json').read_text())
result = json.loads((root / 'test.json').read_text())
metrics = pd.DataFrame(result['metrics']).groupby('model')[['qlike', 'mse']].mean()
qlike_winner = metrics.qlike.idxmin()
mse_winner = metrics.mse.idxmin()
complex_rows = [row for row in rows if row['model'] in ('garch', 'ridge')]
robust_gains = [row['model'] for row in complex_rows if all(ci[1] < 0 for ci in row['intervals'].values())]
if robust_gains:
    interpretation = ('The descriptive paired intervals favor ' + ', '.join(robust_gains)
                      + ' over EWMA at every tested block length in this case study.')
else:
    interpretation = ('No complex model has a descriptive paired interval entirely below zero '
                      'at every tested block length in this case study; the evidence does not '
                      'establish a consistent advantage over EWMA.')
summary = (f'{qlike_winner.upper()} has the lowest equal-weight aggregate QLIKE '
           f'({metrics.loc[qlike_winner, "qlike"]:.7f}); {mse_winner.upper()} has the lowest '
           f'aggregate MSE ({metrics.loc[mse_winner, "mse"]:.6e}). {interpretation}')
comparisons = []
for row in complex_rows:
    intervals = '; '.join(f'block {block}: [{ci[0]:.5f}, {ci[1]:.5f}]'
                          for block, ci in row['intervals'].items())
    comparisons.append(f'{row["model"].upper()} minus EWMA mean QLIKE is '
                       f'{row["mean_delta"]:.7f} (95% intervals: {intervals}).')
caution = ('Negative differences favor the model. These are descriptive, selection-conditional '
           'intervals without multiple-comparison adjustment. Intervals containing zero do not '
           'establish equivalence or rule out useful gains elsewhere.')
audit = ('This secondary comparison uses the already frozen final-test forecasts to address both '
         'simple baselines. It introduces no new model configurations, refits, hyperparameter '
         'choices or test reruns. Code: scripts/compare_ewma.py. The primary source hash in '
         'frozen.json covers the package as evaluated; these reporting scripts are an additional '
         'transparent analysis of its outputs.')
text = ('## Comparison with the EWMA baseline\n\n' + summary + '\n\n'
        + ' '.join(comparisons) + '\n\n' + caution + '\n\n' + audit + '\n\n'
        + '| Model | Mean Δ vs EWMA | Block 5 CI | Block 20 CI | Block 60 CI |\n'
        + '|---|---:|---|---|---|\n')
for row in rows:
    ci = [f'[{v[0]:.5f}, {v[1]:.5f}]' for v in row['intervals'].values()]
    text += f'| {row["model"]} | {row["mean_delta"]:.7f} | ' + ' | '.join(ci) + ' |\n'
text += ('\n[Machine-readable comparisons](results/ewma_comparisons.json). '
         'The same synchronized block-bootstrap procedure and seed apply.\n\n')
md = docs / 'report.md'
report = md.read_text().replace('## Dependence-aware uncertainty', text + '## Dependence-aware uncertainty')
rows_html = ''.join('<tr><td>' + html.escape(row['model']) + '</td><td>'
                    + f'{row["mean_delta"]:.7f}' + '</td>'
                    + ''.join(f'<td>[{ci[0]:.5f}, {ci[1]:.5f}]</td>'
                              for ci in row['intervals'].values()) + '</tr>' for row in rows)
section = ('<h2>Comparison with the EWMA baseline</h2>'
           + ''.join('<p>' + html.escape(s) + '</p>'
                     for s in [summary, ' '.join(comparisons), caution, audit])
           + '<div class="table-wrap"><table><tr><th>Model</th><th>Mean Δ vs EWMA</th>'
           + '<th>Block 5 CI</th><th>Block 20 CI</th><th>Block 60 CI</th></tr>'
           + rows_html + '</table></div>')
h = docs / 'report.html'
report_html = h.read_text().replace('<h2>Dependence-aware uncertainty</h2>', section + '<h2>Dependence-aware uncertainty</h2>')
# Rendering places the report next to the selected output directory; keep its audit links local.
for original, replacement in [
    ('volatilitylab report --out docs/reproduction', 'python scripts/build_report.py --out reproductions/run1/results'),
    ('docs/reproduction', 'reproductions/run1/results'),
    ('python -m http.server 8000 --directory docs', 'python -m http.server 8000 --directory reproductions/run1'),
    ('(results/', '(' + root.name + '/'),
    ('href="results/', 'href="' + root.name + '/'),
]:
    report = report.replace(original, replacement)
    report_html = report_html.replace(original, replacement)
md.write_text(report)
h.write_text(report_html)
web = json.loads((root / 'explorer.json').read_text())
web['intervals_ewma'] = rows
(root / 'explorer.json').write_text(json.dumps(web, separators=(',', ':'), allow_nan=False))
r = project / 'README.md' if is_published else docs / 'README.md'
s = r.read_text().replace('![Final test comparison]', summary + '\n\n'
                         + ' '.join(comparisons) + '\n\n' + caution
                         + '\n\n![Final test comparison]', 1)
s = s.replace('volatilitylab report --out docs/reproduction', 'python scripts/build_report.py --out reproductions/run1/results')
s = s.replace('docs/reproduction', 'reproductions/run1/results')
s = s.replace('python -m http.server 8000 --directory docs', 'python -m http.server 8000 --directory reproductions/run1')
s = s.replace('Open http://localhost:8000.',
              'Open http://localhost:8000. Each fresh reproduction is rendered as a self-contained '
              'site under reproductions/run1, including its own explorer, report, plots and audit links; '
              'the published docs/results evidence remains unchanged.')
r.write_text(s)
