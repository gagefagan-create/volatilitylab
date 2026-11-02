'use strict';
const colors={historical:'#708191',ewma:'#d16a38',garch:'#187d73',ridge:'#6d63a8'};
const names={historical:'Historical',ewma:'EWMA',garch:'GARCH',ridge:'Ridge'};
const $=s=>document.getElementById(s);
const fmt=(v,metric)=>metric==='mse'?v.toExponential(4):v.toFixed(4);
let data;
function comparison(){
 const symbol=$('symbol').value,metric=$('metric').value;
 const rows=Object.keys(names).map(model=>{const a=data.metrics.filter(r=>r.model===model&&(symbol==='ALL'||r.symbol===symbol));return {model,value:a.reduce((s,r)=>s+r[metric],0)/a.length,n:a[0].n};}).sort((a,b)=>a.value-b.value);
 const max=Math.max(...rows.map(r=>r.value))*1.1;
 $('bars').innerHTML=rows.map(r=>`<div class="bar-row"><span>${names[r.model]}</span><div class="track"><div class="fill" style="width:${r.value/max*100}%;background:${colors[r.model]}"></div></div><span class="value">${fmt(r.value,metric)}</span></div>`).join('');
 $('loss-label').textContent=(metric==='qlike'?'QLIKE':'MSE')+' ↓';
 $('metrics').innerHTML=rows.map(r=>`<tr><td>${names[r.model]}</td><td class="value">${fmt(r.value,metric)}</td><td><code>${JSON.stringify(data.selected[r.model])}</code></td><td>${r.n}</td></tr>`).join('');
}
function path(){
 const symbol=$('path-symbol').value, model=$('path-model').value,p=data.paths[symbol];
 const actual=p.target.map(v=>100*Math.sqrt(252*v/5)),forecast=p.forecasts[model].map(v=>100*Math.sqrt(252*v/5));
 const max=Math.max(...actual,...forecast)*1.1;
 const xy=a=>a.map((v,i)=>`${(55+i/(a.length-1)*920).toFixed(2)},${(263-v/max*233).toFixed(2)}`).join(' ');
 let svg='<title>'+symbol+' observed and '+names[model]+' forecast, annualized standard deviation</title>';
 for(let i=0;i<=4;i++){const v=max*i/4,y=263-v/max*233;svg+=`<line x1="55" x2="975" y1="${y}" y2="${y}" stroke="#dce2dc"/><text x="43" y="${y+4}" text-anchor="end" font-size="11" fill="#5d6f79">${v.toFixed(0)}%</text>`;}
 for(let i=0;i<4;i++){const idx=Math.floor(i*(p.dates.length-1)/3);svg+=`<text x="${55+idx/(p.dates.length-1)*920}" y="292" text-anchor="middle" font-size="11" fill="#5d6f79">${p.dates[idx]}</text>`;}
 svg+=`<polyline points="${xy(actual)}" fill="none" stroke="#9daab3" stroke-width="1"/><polyline points="${xy(forecast)}" fill="none" stroke="${colors[model]}" stroke-width="1.5"/>`;
 $('path').innerHTML=svg;$('path-summary').textContent=`${symbol} · ${names[model]} · ${p.dates[0]} to ${p.dates.at(-1)} · ${p.dates.length} daily forecast origins. The observed proxy contains five forward daily returns.`;
}
function intervals(){
 const b=$('block').value; const reference=$('reference').value; const rows=reference==='ewma'?data.intervals_ewma:data.intervals;
 $('intervals').innerHTML=rows.map(r=>{const ci=r.intervals[b];return `<tr><td>${names[r.model]}</td><td class="value">${r.mean_delta.toFixed(4)}</td><td class="value">[${ci[0].toFixed(4)}, ${ci[1].toFixed(4)}]</td><td>${r.model===reference?'Reference':ci[1]<0?'Lower loss in this paired comparison':ci[0]>0?'Higher loss in this paired comparison':'Interval includes zero'}</td></tr>`;}).join('');
}
fetch('results/explorer.json').then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();}).then(d=>{
 data=d;
 const means=Object.keys(names).map(model=>({model,v:d.metrics.filter(r=>r.model===model).reduce((s,r)=>s+r.qlike,0)/3})).sort((a,b)=>a.v-b.v);
 $('finding').textContent='Complexity offers no clear gain over EWMA.';
 $('finding-detail').textContent=`Ridge leads QLIKE by just 0.0000824 versus EWMA; paired intervals include zero. EWMA has the lowest MSE. Inspect the ETF differences and uncertainty below.`;
 $('trials').innerHTML='<table><thead><tr><th>Configuration</th><th>Validation QLIKE</th></tr></thead><tbody>'+d.trials.map(t=>`<tr><td><code>${JSON.stringify(t.configuration)}</code></td><td>${t.validation_qlike===null?'FAILED':t.validation_qlike.toFixed(4)}</td></tr>`).join('')+'</tbody></table>';
 comparison();path();intervals();
 for(const id of ['symbol','metric'])$(id).addEventListener('change',comparison);
 for(const id of ['path-symbol','path-model'])$(id).addEventListener('change',path);
 $('block').addEventListener('change',intervals); $('reference').addEventListener('change',intervals);
}).catch(e=>{$('finding').textContent='Results could not be loaded.';$('finding-detail').textContent='Serve this directory over HTTP or open the full report. '+e.message;});
