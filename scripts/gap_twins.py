"""시범 분석 2: 쌍둥이 시군구와 견준 공백 점수.

공급 지표: 발달장애인 주간활동, 방과후활동 제공기관 수 (providers.py, 전자바우처 API 2026-11-08)
나눌 수: 서비스 나이대(6~64세) 발달장애인 수 (복지로 2026-09, bokjiro.py). 1천 명당 기관 수로 본다.
쌍둥이: twins.py 결과 (out/tables/twins.csv), 같은 종류(시, 군, 자치구)에서 가장 닮은 5곳
공백 점수: 우리 값 / 쌍둥이 중앙값. 1보다 작으면 닮은 지역보다 공급이 적다. 0 이면 기관이 없다.

사용:  python3 -I scripts/gap_twins.py [시군구 ...]     (기본: 경북 시군)
결과:  out/tables/gap_twins.csv
"""

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bokjiro
import providers
from common import OUT, SHORT, read_csv, write_csv

PER = 1_000


def main(names):
    feats = {(r["시도"], r["시군구"]): r for r in read_csv(OUT / "tables" / "twins_features.csv")}
    twins = {}
    for r in read_csv(OUT / "tables" / "twins.csv"):
        twins.setdefault((r["시도"], r["시군구"]), []).append((r["쌍둥이_시도"], r["쌍둥이_시군구"]))
    sup, dem = providers.counts(), bokjiro.counts()
    missing = [u for u in feats if not dem[u]["발달_6_64"]]
    if missing:
        sys.exit(f"복지로 자료에 발달장애인이 없는 단위: {missing}")
    rate = {u: sup[u]["제공기관"] / dem[u]["발달_6_64"] * PER for u in feats}
    rows = []
    for u, tw in twins.items():
        med = statistics.median(rate[t] for t in tw)
        rows.append({
            "시도": u[0], "시군구": u[1], "인구": feats[u]["인구"], "발달장애인_6_64": dem[u]["발달_6_64"],
            "제공기관": sup[u]["제공기관"],
            "기관_1천명당": round(rate[u], 2), "쌍둥이_중앙값": round(med, 2),
            "공백점수": round(rate[u] / med, 2) if med else "",
            "쌍둥이": ", ".join(f"{SHORT[t[0]]} {t[1]} {rate[t]:.2f}" for t in tw),
        })
    write_csv(OUT / "tables" / "gap_twins.csv", rows, list(rows[0]))
    want = [r for r in rows if (r["시군구"] in names if names else r["시도"] == "경상북도")]
    want.sort(key=lambda r: (r["공백점수"] == "", r["공백점수"] if r["공백점수"] != "" else 0))
    zero = sum(1 for r in rows if r["제공기관"] == 0)
    print(f"전국 {len(rows)}개 단위, 제공기관 {sum(r['제공기관'] for r in rows):,}곳, 기관 없는 단위 {zero}곳, "
          f"발달장애인(6~64세) {sum(r['발달장애인_6_64'] for r in rows):,}명, 1천 명당 {sum(r['제공기관'] for r in rows) / sum(r['발달장애인_6_64'] for r in rows) * PER:.2f}곳")
    for r in want:
        print(f"{r['시군구']:<5} 1천 명당 {r['기관_1천명당']:>5} | 쌍둥이 중앙값 {r['쌍둥이_중앙값']:>5} | "
              f"공백점수 {r['공백점수']:>5} | {r['쌍둥이']}")


if __name__ == "__main__":
    main(sys.argv[1:])
