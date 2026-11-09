"""Offline evidence viewer. Values come from recorded experiment outputs."""
from __future__ import annotations
import html
import json
from pathlib import Path
from typing import Any


def write_report(summary: dict[str, Any], path: Path) -> None:
    body = json.dumps(summary).replace("<", "\\u003c").replace("&", "\\u0026")
    template = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Deadline Lab | Evidence workbench</title>
<style>
:root{font-family:system-ui,-apple-system,sans-serif;color:#e3ebf0;background:#0d1720;font-size:15px}
body{max-width:1160px;margin:0 auto;padding:38px 24px 64px}h1{font-size:42px;letter-spacing:-1.8px;margin:12px 0}
h2{margin-top:32px;font-size:22px}p{line-height:1.6;max-width:920px;color:#b7c6d2}.eyebrow{letter-spacing:2px;font-size:12px;color:#74d6bd}
.banner{padding:16px 20px;border-left:3px solid #e8b45b;background:#20282c;line-height:1.5}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}
.card{padding:20px;border:1px solid #2e424e;border-radius:10px;background:#13232d}.number{font-size:32px;font-weight:650;display:block}.label{font-size:13px;color:#a5bac8}
table{border-collapse:collapse;width:100%;background:#13232d;font-size:14px}th,td{padding:13px 16px;text-align:left;border-bottom:1px solid #2a3d49}th{color:#9db3c2;font-weight:500}
.good{color:#7de0ba}.bad{color:#f4a68c}.unknown{color:#e8b45b}button,select{background:#1e3443;border:1px solid #45606f;border-radius:6px;color:#eef5f8;padding:10px;font:inherit;cursor:pointer}
pre{overflow:auto;background:#081118;padding:18px;border-radius:8px;font-size:12px;line-height:1.6;max-height:500px}details{margin:16px 0;border:1px solid #2e424e;padding:16px;border-radius:8px}summary{cursor:pointer}code{font-family:ui-monospace,monospace}footer{margin-top:38px;color:#8099a9;font-size:12px}.split{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
@media(max-width:700px){.cards{grid-template-columns:1fr 1fr}h1{font-size:32px}body{padding:24px 12px}th,td{padding:10px 6px;font-size:12px}}
</style>
<div class="eyebrow">WHYME LABS / LOCAL ENGINEERING EVIDENCE</div>
<h1>Recovery is more than a restart.</h1>
<p>Generate fault sequences. Observe effects in a separate virtual plant. Reduce a failing sequence. Keep the result as a regression test.</p>
<div class="banner"><strong>Evidence level: Linux processes and a synthetic plant.</strong> C controller fixtures were compiled and executed locally. QNX-native code is scaffolded, not compiled or run. Every defect shown here is deliberately seeded. No physical actuator or production application was tested.</div>
<div class="cards" id="cards"></div>
<h2>Mutation sensitivity and healthy progress</h2>
<p>The reference implementation must continue to accept a fresh healthy command. A controller that rejects everything is a failing negative control, not a safe pass.</p>
<table><thead><tr><th>Implementation</th><th>Runs</th><th>Pass</th><th>Fail</th><th>Inconclusive</th><th>Effects</th></tr></thead><tbody id="modes"></tbody></table>
<h2>Failure to regression</h2>
<p>These witnesses were reduced by repeatedly launching real processes. “1-minimal” means no single valid action deletion retained the selected failure in the repeated checks. It does not mean globally shortest or deterministic OS scheduling.</p>
<div id="witnesses"></div>
<h2>Recorded campaign</h2>
<div class="split"><label for="filter">Filter by implementation</label><select id="filter"><option value="all">All</option></select><span id="count"></span></div>
<table style="margin-top:16px"><thead><tr><th>Seed / split</th><th>Implementation</th><th>Verdict</th><th>Violated properties</th><th>Actions</th></tr></thead><tbody id="runs"></tbody></table>
<footer>No external libraries, network calls or telemetry. Raw JSON, effect traces, build evidence and checksums accompany this viewer. Authorisation timestamps do not prove a physical actuation deadline.</footer>
<script id="data" type="application/json">__DATA__</script>
<script>
const d=JSON.parse(document.getElementById('data').textContent);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stats=d.modes||{};
const cards=[['Scenario executions',d.runs.length],['Generated histories',d.scenarios],['Reduced witnesses',(d.witnesses||[]).length],['QNX target runs',0]];
document.getElementById('cards').innerHTML=cards.map(([a,b])=>`<div class="card"><span class="number">${esc(b)}</span><span class="label">${esc(a)}</span></div>`).join('');
document.getElementById('modes').innerHTML=Object.entries(stats).map(([m,s])=>`<tr><td>${esc(m)}</td><td>${s.runs}</td><td class="good">${s.PASS}</td><td class="bad">${s.FAIL}</td><td class="unknown">${s.INCONCLUSIVE}</td><td>${s.effects}</td></tr>`).join('');
for(const m of Object.keys(stats)){let o=document.createElement('option');o.value=m;o.textContent=m;document.getElementById('filter').append(o)}
function render(){const f=document.getElementById('filter').value;const rows=d.runs.filter(r=>f==='all'||r.mode===f);document.getElementById('count').textContent=`${rows.length} runs`;document.getElementById('runs').innerHTML=rows.map(r=>`<tr><td>${r.seed} / ${esc(r.split)}</td><td>${esc(r.mode)}</td><td class="${r.verdict==='PASS'?'good':r.verdict==='FAIL'?'bad':'unknown'}">${esc(r.verdict)}</td><td>${esc(r.properties.join(', ')||'none')}</td><td>${r.action_count}</td></tr>`).join('')}
document.getElementById('filter').addEventListener('change',render);render();
document.getElementById('witnesses').innerHTML=(d.witnesses||[]).map(w=>`<details open><summary><strong>${esc(w.property)}</strong> · ${w.input_actions} → ${w.witness_actions} actions · reference replays ${w.reference_passes}/${w.reference_replays}</summary><p>Faulty fixture replays ${w.mutant_failures}/${w.mutant_replays}. Deletion-1-minimal: ${w.deletion_1_minimal}. ${w.candidate_executions} reduction executions.</p><pre>${esc(JSON.stringify(w.scenario,null,2))}</pre></details>`).join('');
</script></html>'''
    path.write_text(template.replace("__DATA__", body), encoding="utf-8")
