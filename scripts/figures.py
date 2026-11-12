"""제안서 그림 3개를 SVG 로 그리고 Chrome(헤드리스)으로 PNG 를 만든다.

그림 1: 경북 22개 시군의 제공기관 한 곳당 발달장애인(6~64세) 수 (out/tables/gb_dev_gap.csv)
그림 2: 복지 공백 지도 시스템 구조. 오른쪽 '담당자 화면' 의 지도 색은 out/tables/gap_twins.csv 의 실제 공백 점수다
그림 3: 두 시군과 각자의 쌍둥이 5곳의 발달장애인(6~64세) 1천 명당 제공기관 (out/tables/gap_twins.csv)
        청도군은 기관 한 곳당 발달장애인이 경북 평균과 같지만 쌍둥이와 견주면 모자란 예다

인쇄용(한글 문서에 너비 17cm 로 넣는다)이라 마우스 올림, 어두운 화면 모드는 없다. 모든 값은 out/tables 의 표에 있다.
제출물 규칙: 그림 안 글자에도 가운뎃점, 화살표 문자, 줄표 같은 특수문자를 쓰지 않는다 (화살표는 도형으로 그린다).
색: 막대는 한 가지 파랑(강조), 견줄 대상은 회색, 지도는 파랑 한 가지 색의 4단계 (dataviz 검사 통과).

사용:  python3 -I scripts/figures.py          (gb_dev_gap.py, twins.py, gap_twins.py 다음에)
결과:  out/fig/<이름>.png, out/fig/html/<이름>.html
"""

import html
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, read_csv

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FIG = OUT / "fig"
W = 900
M = 12  # 좌우 여백
IW = W - 2 * M
FONT = '"Apple SD Gothic Neo", "Malgun Gothic", sans-serif'
SURFACE, INK, INK2, MUTED = "#ffffff", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, NEUTRAL, PANEL = "#e1e0d9", "#c3c2b7", "#f0efec", "#f7f7f5"
BLUE, GRAY = "#2a78d6", "#c3c2b7"
RAMP = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # 공백 작음에서 큼으로 (0.8 이상, 0.5~0.8, 0.5 미만, 기관 없음)
RAMP_INK = [INK, "#ffffff", "#ffffff", "#ffffff"]


def esc(s):
    return html.escape(str(s), quote=True)


def text(x, y, s, size=15, fill=INK, anchor="start", weight=400, extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}" {extra}>{esc(s)}</text>')


def col_path(x, y_top, w, y_base, r=4):
    """세로 막대: 값 쪽 끝만 4px 둥글게, 바닥은 각지게."""
    r = min(r, w / 2, max(y_base - y_top, 0))
    return (f'<path d="M{x:.1f},{y_base:.1f} V{y_top + r:.1f} Q{x:.1f},{y_top:.1f} {x + r:.1f},{y_top:.1f} '
            f'H{x + w - r:.1f} Q{x + w:.1f},{y_top:.1f} {x + w:.1f},{y_top + r:.1f} V{y_base:.1f} Z"')


def bar_path(x0, y, x1, h, r=4):
    """가로 막대: 값 쪽 끝(오른쪽)만 4px 둥글게."""
    r = min(r, h / 2, max(x1 - x0, 0))
    return (f'<path d="M{x0:.1f},{y:.1f} H{x1 - r:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} '
            f'V{y + h - r:.1f} Q{x1:.1f},{y + h:.1f} {x1 - r:.1f},{y + h:.1f} H{x0:.1f} Z"')


def svg(w, h, body):
    """안쪽 너비 IW 로 그린 내용을 좌우 M 여백을 두고 감싼다. 위아래도 M 씩."""
    h = h + 2 * M
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family=\'{FONT}\' style="font-variant-numeric: tabular-nums">'
            f'<rect width="{w}" height="{h}" fill="{SURFACE}"/><g transform="translate({M},{M})">{body}</g></svg>'), h


def r0(v):
    """반올림(0.5 는 올림). 파이썬 기본 반올림은 132.5 를 132 로 만든다."""
    return int(math.floor(v + 0.5))


def short(name):
    return name[:-1] if name.endswith(("시", "군")) else name


def josa(word, batchim, plain):
    """받침이 있으면 앞의 조사, 없으면 뒤의 조사 (예: 성주군과, 안동시와)."""
    c = word[-1]
    has = "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 != 0
    return word + (batchim if has else plain)


# 그림 1 ---------------------------------------------------------------------------------------------

def fig1():
    rows = read_csv(OUT / "tables" / "gb_dev_gap.csv")  # 기관 없는 시군이 먼저, 그다음 기관당 인원이 많은 순
    left, right, top, plot_h = 46, 4, 50, 230
    base = top + plot_h
    n = len(rows)
    slot = (IW - left - right) / n
    cw = min(24, slot * 0.62)
    vmax = max(float(r["발달장애인_기관당"]) for r in rows if r["발달장애인_기관당"])
    step = 100 if vmax < 800 else 200
    ymax = step * math.ceil(vmax * 1.12 / step)
    y = lambda v: base - v / ymax * plot_h
    out = [text(0, 16, "제공기관 한 곳당 발달장애인 (6~64세, 명)", 15, INK2)]
    for v in range(0, ymax + 1, step):
        out.append(f'<line x1="{left}" x2="{IW - right}" y1="{y(v):.1f}" y2="{y(v):.1f}" '
                   f'stroke="{AXIS if v == 0 else GRID}" stroke-width="1"/>')
        out.append(text(left - 8, y(v) + 5, f"{v:,}", 14, MUTED, "end"))
    none = [i for i, r in enumerate(rows) if not r["발달장애인_기관당"]]
    if none:
        x0, x1 = left + none[0] * slot + 2, left + (none[-1] + 1) * slot - 2
        out.append(f'<rect x="{x0:.1f}" y="{top:.1f}" width="{x1 - x0:.1f}" height="{plot_h - 1:.1f}" fill="{NEUTRAL}"/>')
        ym = top + plot_h * 0.62  # 옆 막대의 값 글자와 같은 높이에 오지 않게 띠 가운데쯤에
        out.append(text((x0 + x1) / 2, ym, "기관", 14, INK, "middle", 600))
        out.append(text((x0 + x1) / 2, ym + 18, "없음", 14, INK, "middle", 600))
    vals = [(float(r["발달장애인_기관당"]), i) for i, r in enumerate(rows) if r["발달장애인_기관당"]]
    hi = sorted(vals, reverse=True)[:2]
    lo = min(vals)
    label_at = {i for _, i in hi} | {lo[1]}
    for i, r in enumerate(rows):
        cx = left + (i + 0.5) * slot
        if r["발달장애인_기관당"]:
            v = float(r["발달장애인_기관당"])
            out.append(col_path(cx - cw / 2, y(v), cw, base) + f' fill="{BLUE}"/>')
            if i in label_at:
                out.append(text(cx, y(v) - 7, f"{r0(v):,}", 15, INK, "middle", 700))
        out.append(text(cx, base + 21, short(r["시군"]), 15, INK if i in none else INK2, "middle",
                        600 if i in none else 400))
    dev = sum(int(r["발달장애인_6_64"]) for r in rows)
    org = sum(int(r["제공기관"]) for r in rows)
    avg = dev / org
    out.append(f'<line x1="{left}" x2="{IW - right}" y1="{y(avg):.1f}" y2="{y(avg):.1f}" stroke="{INK2}" stroke-width="1.2"/>')
    out.append(text(IW - right, y(avg) - 7, f"경북 전체 {r0(avg):,}명", 14, INK2, "end", 600,
                    f'stroke="{SURFACE}" stroke-width="4" paint-order="stroke"'))
    notes = ["자료: 복지로 사회보장통계 장애인등록 장애유형별 연령별 장애인수(2026년 9월), 사회서비스 전자바우처 제공기관(2026년 11월 8일 조회).",
             "발달장애인은 지적, 자폐성 장애인입니다. 방과후활동(6~17세)과 주간활동(18세 이상) 대상 가운데 6~64세만 셌습니다.",
             "제공기관은 발달장애인 주간활동이나 청소년 방과후활동을 하는 기관입니다."]
    for k, s in enumerate(notes):
        out.append(text(0, base + 52 + k * 18, s, 13, MUTED))
    h = base + 52 + (len(notes) - 1) * 18 + 6
    page, h = svg(W, h, "".join(out))
    return page, W, h


# 그림 3 ---------------------------------------------------------------------------------------------

def twin_panel(r, x0, pw, xmax, plot_top, row_h=30, bar_h=16, step=2):
    label_w, val_w = 98, 40
    px0, px1 = x0 + label_w, x0 + pw - val_w
    xs = lambda v: px0 + v / xmax * (px1 - px0)
    focal = (f"경북 {r['시군구']}", float(r["기관_1천명당"]))
    twins = []
    for part in r["쌍둥이"].split(", "):
        name, v = part.rsplit(" ", 1)
        twins.append((name, float(v)))
    twins.sort(key=lambda t: -t[1])
    items = [focal] + twins
    med = float(r["쌍둥이_중앙값"])
    kind = "시" if r["시군구"].endswith("시") else "군"
    out = [text(x0, 22, f"{josa(r['시군구'], '과', '와')} 쌍둥이 {kind} 5곳", 17, INK, "start", 700),
           text(x0, 46, f"공백 점수 {float(r['공백점수']):.2f}", 15, INK2)]
    bottom = plot_top + len(items) * row_h
    for v in range(0, int(xmax) + 1, step):
        out.append(f'<line x1="{xs(v):.1f}" x2="{xs(v):.1f}" y1="{plot_top - 4}" y2="{bottom}" '
                   f'stroke="{AXIS if v == 0 else GRID}" stroke-width="1"/>')
        out.append(text(xs(v), bottom + 18, str(v), 14, MUTED, "middle"))
    labels = []
    for k, (name, v) in enumerate(items):
        yb = plot_top + k * row_h + (row_h - bar_h) / 2
        is_focal = k == 0
        out.append(bar_path(px0, yb, xs(v), bar_h) + f' fill="{BLUE if is_focal else GRAY}"/>')
        out.append(text(px0 - 8, yb + bar_h - 3, name, 15, INK if is_focal else INK2, "end", 700 if is_focal else 400))
        labels.append(text(xs(v) + 6, yb + bar_h - 3, f"{v:.2f}", 14, INK, "start", 700 if is_focal else 400,
                           f'stroke="{SURFACE}" stroke-width="5" paint-order="stroke"'))
    out.append(f'<line x1="{xs(med):.1f}" x2="{xs(med):.1f}" y1="{plot_top - 10}" y2="{bottom}" stroke="{INK2}" stroke-width="1.2"/>')
    out.append(text(xs(med) + 5, plot_top - 12, f"쌍둥이 중앙값 {med:.2f}", 13, INK2, "start", 600))
    out += labels
    return "".join(out), bottom


def fig3(names=("안동시", "청도군")):
    rows = {r["시군구"]: r for r in read_csv(OUT / "tables" / "gap_twins.csv") if r["시도"] == "경상북도"}
    pick = [rows[n] for n in names]
    vals = [float(r["기관_1천명당"]) for r in pick] + [float(p.rsplit(" ", 1)[1]) for r in pick for p in r["쌍둥이"].split(", ")]
    step = 1 if max(vals) <= 6 else 2 if max(vals) <= 12 else 5
    xmax = step * math.ceil(max(vals) / step)
    gutter = 44
    pw = (IW - gutter) / 2
    body, bottom = [], 0
    for k, r in enumerate(pick):
        s, bottom = twin_panel(r, k * (pw + gutter), pw, xmax, plot_top=78, step=step)
        body.append(s)
    notes = ["발달장애인(6~64세) 1천 명당 주간활동, 방과후활동 제공기관 수(곳). 쌍둥이는 인구 규모, 나이 구조, 수급률 등 7개 지표가",
             "가장 닮은 전국의 같은 종류(시는 시, 군은 군) 5곳입니다. 공백 점수는 우리 값을 쌍둥이 중앙값으로 나눈 값으로,",
             "1보다 작을수록 모자랍니다. 자료: 복지로 연령별 등록장애인(2026년 9월), 주민등록 인구(2026년 10월),",
             "시군구별 수급권자(2025년 12월), 사회서비스 전자바우처 제공기관(2026년 11월 8일 조회)."]
    for k, s in enumerate(notes):
        body.append(text(0, bottom + 50 + k * 18, s, 13, MUTED))
    h = bottom + 50 + (len(notes) - 1) * 18 + 6
    page, h = svg(W, h, "".join(body))
    return page, W, h


# 그림 2 ---------------------------------------------------------------------------------------------

TILES = {  # 경북 시군의 대략적인 위치 (열: 서에서 동, 행: 북에서 남). 울릉은 동쪽 바다에 따로
    "영주시": (2, 0), "봉화군": (3, 0), "울진군": (4, 0),
    "문경시": (0, 1), "예천군": (1, 1), "안동시": (2, 1), "영양군": (3, 1),
    "상주시": (0, 2), "의성군": (2, 2), "청송군": (3, 2), "영덕군": (4, 2),
    "김천시": (0, 3), "구미시": (1, 3), "포항시": (4, 3),
    "성주군": (0, 4), "칠곡군": (1, 4), "영천시": (3, 4), "경주시": (4, 4),
    "고령군": (0, 5), "경산시": (2, 5),
    "청도군": (2, 6),
    "울릉군": (5, 0),
}


def gap_class(r):
    if int(r["제공기관"]) == 0:
        return 3
    g = float(r["공백점수"])
    return 2 if g < 0.5 else 1 if g < 0.8 else 0


def arrow(x1, y1, x2, y2):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{INK2}" stroke-width="2" '
            f'marker-end="url(#head)"/>')


def fig2(plan="안동시"):
    rows = {r["시군구"]: r for r in read_csv(OUT / "tables" / "gap_twins.csv") if r["시도"] == "경상북도"}
    per = {r["시군"]: r for r in read_csv(OUT / "tables" / "gb_dev_gap.csv")}
    top, bot = 42, 388
    out = ['<defs><marker id="head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
           f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="{INK2}"/></marker></defs>']
    mid = (top + bot) / 2
    # 왼쪽: 데이터
    ax, aw = 0, 196
    out.append(text(ax, 18, "공개 사회보장 데이터", 16, INK, "start", 700))
    out.append(f'<rect x="{ax + 0.5}" y="{top}" width="{aw}" height="{bot - top}" rx="8" fill="{PANEL}" stroke="{GRID}"/>')
    groups = [("수요", ["연령별 등록장애인 (복지로)", "시군구별 수급권자", "주민등록 인구"]),
              ("공급", ["지자체 복지사업 (API)", "사회서비스 제공기관 (API)", "사회복지시설 (API)", "장애인 주간이용시설"])]
    yy = top + 34
    for title, items in groups:
        out.append(text(ax + 14, yy, title, 15, INK, "start", 700))
        yy += 27
        for it in items:
            out.append(text(ax + 14, yy, it, 14.5, INK2))
            yy += 27
        yy += 26
    out.append(text(ax + 14, bot - 16, "시군구 단위로 결합", 13.5, INK, "start", 600))
    # 가운데: AI 4단계
    bx, bw = 230, 282
    out.append(text(bx, 18, "AI 분석 4단계", 16, INK, "start", 700))
    steps = [("사업 정리", "LLM 정보 추출, 같은 기관 묶기"),
             ("쌍둥이 시군구", "인구, 나이 구조, 수급률 7개 지표"),
             ("공백 점수", "수요 대비 공급을 쌍둥이와 비교"),
             ("사업 설계 에이전트", "RAG, 근거 붙은 사업계획 초안")]
    gap = 14
    sh = (bot - top - gap * (len(steps) - 1)) / len(steps)
    for k, (t, sub) in enumerate(steps):
        y0 = top + k * (sh + gap)
        out.append(f'<rect x="{bx + 0.5}" y="{y0:.1f}" width="{bw}" height="{sh:.1f}" rx="8" fill="{PANEL}" stroke="{GRID}"/>')
        out.append(f'<circle cx="{bx + 28}" cy="{y0 + sh / 2:.1f}" r="14" fill="{BLUE}"/>')
        out.append(text(bx + 28, y0 + sh / 2 + 5.5, str(k + 1), 15, "#ffffff", "middle", 700))
        out.append(text(bx + 54, y0 + sh / 2 - 5, t, 16, INK, "start", 700))
        out.append(text(bx + 54, y0 + sh / 2 + 18, sub, 13.5, INK2))
        if k < len(steps) - 1:
            out.append(arrow(bx + 28, y0 + sh + 1, bx + 28, y0 + sh + gap - 1))
    out.append(arrow(ax + aw + 4, mid, bx - 6, mid))
    # 오른쪽: 담당자 화면 (지도는 실제 공백 점수)
    cx0 = 548
    out.append(arrow(bx + bw + 4, mid, cx0 - 8, mid))
    out.append(text(cx0, 18, "담당자 화면 (경북 시범 결과)", 16, INK, "start", 700))
    tile, pitch, mx, my = 29, 33, cx0, top
    for name, (c, rr) in TILES.items():
        x = mx + c * pitch + (8 if name == "울릉군" else 0)
        yv = my + rr * pitch
        k = gap_class(rows[name])
        out.append(f'<rect x="{x}" y="{yv}" width="{tile}" height="{tile}" rx="4" fill="{RAMP[k]}"/>')
        out.append(text(x + tile / 2, yv + tile / 2 + 4.5, short(name), 12, RAMP_INK[k], "middle", 600))
    x, yv = mx + 2 * pitch, my + 4 * pitch
    out.append(f'<rect x="{x}" y="{yv}" width="{tile}" height="{tile}" rx="4" fill="{NEUTRAL}"/>')
    out.append(text(x + tile / 2, yv + tile / 2 + 4.5, "대구", 12, MUTED, "middle", 600))
    lx = mx + 6 * pitch + 22
    out.append(text(lx, my + 13, "공백 점수", 13.5, INK, "start", 700))
    legend = ["0.8 이상", "0.5~0.8", "0.5 미만", "기관 없음"]
    for k, lab in enumerate(legend):
        ly = my + 26 + k * 25
        out.append(f'<rect x="{lx}" y="{ly}" width="15" height="15" rx="3" fill="{RAMP[k]}"/>')
        out.append(text(lx + 21, ly + 12.5, lab, 13, INK2))
    for k, s in enumerate(["1보다 작을수록", "닮은 지역보다", "공급이 적음"]):
        out.append(text(lx, my + 26 + 4 * 25 + 14 + k * 17, s, 12.5, MUTED))
    py0 = my + 7 * pitch + 8
    out.append(f'<rect x="{cx0 + 0.5}" y="{py0}" width="{IW - cx0 - 1}" height="{bot - py0}" rx="8" fill="{PANEL}" stroke="{GRID}"/>')
    lines = [(f"사업계획 초안: {plan} 주간활동 기관 확충", INK, 700),
             (f"기관 한 곳당 발달장애인 {r0(float(per[plan]['발달장애인_기관당'])):,}명, "
              f"공백 점수 {float(rows[plan]['공백점수']):.2f}", INK2, 400),
             ("참고 사업, 대상자 수, 예산 추정, 출처와 기준 시점", INK2, 400)]
    for k, (s, color, wgt) in enumerate(lines):
        out.append(text(cx0 + 14, py0 + 23 + k * 20, s, 13.5, color, "start", wgt))
    page, h = svg(W, bot + 2, "".join(out))
    return page, W, h


# 출력 -----------------------------------------------------------------------------------------------

FIGURES = [("fig1_gb_dev_gap", fig1), ("fig2_system", fig2), ("fig3_twins", fig3)]


def render():
    (FIG / "html").mkdir(parents=True, exist_ok=True)
    for key, fn in FIGURES:
        content, w, h = fn()
        page = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{key}</title>'
                f'<style>html,body{{margin:0;padding:0;background:{SURFACE}}}svg{{display:block}}</style>'
                f'</head><body>{content}</body></html>')
        hp = FIG / "html" / f"{key}.html"
        hp.write_text(page, encoding="utf-8")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                        f"--window-size={w},{int(math.ceil(h))}", f"--screenshot={FIG / (key + '.png')}", hp.as_uri()],
                       check=True, capture_output=True)
        print(f"✔ out/fig/{key}.png ({w}x{int(math.ceil(h))}, 2배)")


if __name__ == "__main__":
    render()
