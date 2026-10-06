"""STEP 8 진단 보고서 (인쇄용 HTML). 브라우저의 인쇄 기능으로 PDF 로 저장한다."""
from __future__ import annotations

from html import escape

from ..models import DiagnosisRun, Process

_STATUS = {"met": ("충족", "#1e7e46"), "partial": ("부분", "#b05c1a"), "unmet": ("미흡", "#c0392b"),
           "pending": ("확인 대기", "#6b7280"), "na": ("해당 없음", "#9ca3af")}


def render_report(process: Process, dr: DiagnosisRun) -> str:
    s = dr.summary
    e = escape
    rows = []
    for a in s["areas"]:
        pct = "—" if a["pct"] is None else f"{a['pct']}%"
        rows.append(f"<tr><td>{e(a['name'])}</td><td class=n>{a['items']}</td><td class=n>{a['score']:g}</td>"
                    f"<td class=n>{pct}</td><td class=n>{a['auto']}</td><td class=n>{a['manual']}</td>"
                    f"<td class=n>{a['implemented']} / {a['guideline_items']}</td></tr>")
    items = []
    for it in dr.items:
        label, color = _STATUS[it["status"]]
        ds = "".join(f"<li>{e(d['name'])} — {e(d['detail'])}</li>" for d in it["datasets"] if d["status"] != "met")
        ev = "<br>".join(e(x) for x in it["evidence"])
        items.append(f"<tr><td>{e(it['id'])}</td><td>{e(it['name'])}<div class=s>{e(it['basis'])}</div></td>"
                     f"<td>{e(it['method'])}</td><td style='color:{color};font-weight:700'>{label}</td>"
                     f"<td>{ev}{'<ul>' + ds + '</ul>' if ds else ''}</td></tr>")
    road = "".join(f"<tr><td class=n>{r['rank']}</td><td>{e(r['name'])}<div class=s>{e(r['action'])}</div></td>"
                   f"<td class=n>+{r['gain']:g}</td><td>{e(r['difficulty'])}</td><td class=s>{e(r['basis'])}</td></tr>"
                   for r in s["roadmap"])
    pct = round(dr.score / dr.max_score * 100) if dr.max_score else 0
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>가이드라인 준수 진단 보고서 — {e(process.name)}</title>
<style>
body{{font-family:'Pretendard','Malgun Gothic','Apple SD Gothic Neo',sans-serif;color:#111318;margin:32px;font-size:12px;line-height:1.6}}
h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:14px;margin:24px 0 8px;border-bottom:2px solid #1F2430;padding-bottom:4px}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #D1D5DB;padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#F5F6F8;font-size:11px}} .n{{text-align:right;white-space:nowrap}} .s{{color:#6b7280;font-size:10.5px}}
ul{{margin:4px 0 0 16px;padding:0}} .box{{background:#F5F6F8;border:1px solid #E5E7EB;border-radius:8px;padding:10px 14px}}
.score{{font-size:28px;font-weight:800}} @media print{{body{{margin:12mm}}}}
</style></head><body>
<h1>가이드라인 준수 진단 보고서</h1>
<div class=s>{e(s['guideline'])} · 규칙 세트 {e(dr.ruleset_version)} · 실행 {dr.ended_at:%Y-%m-%d %H:%M} UTC</div>
<h2>대상</h2>
<div class=box><b>{e(process.name)}</b> · 조합 「{e(process.combo_title or '')}」 · 데이터셋 {s['dataset_count']}건 · {'발행' if s['mode'] == 'publish' else '초안'} 모드</div>
<h2>총점</h2>
<div class=box><span class=score>{dr.score:g}</span> / {dr.max_score:g}점 ({pct}%) ·
충족 {s['counts']['met']} · 부분 {s['counts']['partial']} · 미흡 {s['counts']['unmet']} · 확인 대기 {s['counts']['pending']} · 해당 없음 {s['counts']['na']}
<div class=s style="margin-top:6px">{e(s['note'])}</div></div>
<h2>영역별 충족률</h2>
<table><tr><th>영역</th><th>판정 항목</th><th>점수</th><th>충족률</th><th>자동</th><th>수기</th><th>구현 / 가이드라인 항목 수</th></tr>{''.join(rows)}</table>
<h2>조치 우선순위</h2>
<table><tr><th>순위</th><th>조치</th><th>가산</th><th>난이도</th><th>근거</th></tr>{road or '<tr><td colspan=5>조치할 항목이 없습니다</td></tr>'}</table>
<h2>항목별 판정</h2>
<table><tr><th>ID</th><th>항목 · 근거</th><th>판정 방식</th><th>판정</th><th>증거</th></tr>{''.join(items)}</table>
</body></html>"""
