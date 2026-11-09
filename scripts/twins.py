"""쌍둥이 시군구: 인구 구조와 수급 구조가 닮은 기초자치단체를 짝짓는다.

같은 종류(시, 군, 광역시 자치구)끼리만 짝짓는다. 특성 7개 (전부 z 점수로 맞춘 뒤 거리):
  인구(로그), 65세 이상 비율, 0~17세 비율,
  기초생활보장 수급률, 기초연금 수급률(65세 이상 대비), 장애인연금 수급률, 차상위 수급률
자료:
  행정안전부_지역별(행정동) 성별 연령별 주민등록 인구수 (2026-10-31)
  한국사회보장정보원_복지사업 시군구별 수급권자 현황 (2025-12)
일반구는 시로 묶는다 (시·군·자치구, 세종, 제주 행정시 2. 인천 개편 구역은 한 단위).
2026 년 광주·전남 통합(전남광주통합특별시)은 2025-12 수급 자료에 맞춰 광주 5개 구와 전남으로 나눈다.

사용:  python3 -I scripts/twins.py [시군구 ...]     (이름을 주면 그 단위의 쌍둥이를 찍는다)
결과:  out/tables/twins_features.csv, out/tables/twins.csv
"""

import collections
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I 로 돌려도 같은 폴더의 common 을 쓴다
from common import OUT, RAW, SHORT, num, read_csv, unit, write_csv

K = 5
FEATURES = ["인구_로그", "65세이상_비율", "0~17세_비율", "기초생활_수급률", "기초연금_수급률", "장애인연금_수급률", "차상위_수급률"]


def population():
    pop = collections.defaultdict(collections.Counter)
    for r in read_csv(RAW / "datagokr" / "15097972.csv"):
        c = pop[unit(r["시도명"], r["시군구명"])]
        c["인구"] += num(r["계"])
        for k, v in r.items():
            m = re.match(r"(\d+)세(?:이상 )?(남자|여자)$", k)
            if m:
                age = int(m.group(1))
                if age >= 65:
                    c["65+"] += num(v)
                elif age <= 17:
                    c["0~17"] += num(v)
    return pop


def recipients():
    rec = collections.defaultdict(collections.Counter)
    for r in read_csv(RAW / "datagokr" / "15062448.csv"):
        if re.match(r".+시.+구$", r["시군구"]):  # 일반구 행은 건너뛴다 (시 합계 행이 따로 있다)
            continue
        rec[unit(r["시도"], r["시군구"])][r["사업명"]] += num(r["수급권자수"])
    return rec


def build():
    pop, rec = population(), recipients()
    rows = []
    for u in sorted(set(pop) & set(rec)):
        p, r = pop[u], rec[u]
        n = p["인구"]
        rows.append({
            "시도": u[0], "시군구": u[1], "인구": n,
            "인구_로그": math.log(n),
            "65세이상_비율": p["65+"] / n,
            "0~17세_비율": p["0~17"] / n,
            "기초생활_수급률": r["기초생활보장(맞춤형급여)"] / n,
            "기초연금_수급률": r["기초연금"] / p["65+"],
            "장애인연금_수급률": r["장애인연금"] / n,
            "차상위_수급률": (r["차상위장애인"] + r["차상위본인부담경감대상자"] + r["차상위자활"]) / n,
        })
    only = (set(pop) ^ set(rec))
    return rows, only


def kind(r):
    """같은 종류끼리만 짝짓는다: 시, 군, 광역시의 자치구. 하는 일과 사업 권한이 달라서다."""
    if r["시군구"].endswith("군"):
        return "군"
    if r["시도"].endswith(("특별시", "광역시")) and r["시도"] != "세종특별자치시":
        return "구"
    return "시"


def zscores(rows):
    z = []
    for f in FEATURES:
        vals = [r[f] for r in rows]
        mu = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals))
        z.append([(v - mu) / sd for v in vals])
    return list(zip(*z))


def main(names):
    rows, only = build()
    z = zscores(rows)
    twins = []
    for i, r in enumerate(rows):
        d = sorted((math.dist(z[i], z[j]), j) for j in range(len(rows))
                   if j != i and kind(rows[j]) == kind(r))[:K]
        twins.append([(rows[j], dist) for dist, j in d])
    feat_rows = [{k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]
    write_csv(OUT / "tables" / "twins_features.csv", feat_rows, list(feat_rows[0]))
    out = []
    for r, tw in zip(rows, twins):
        for rank, (t, dist) in enumerate(tw, 1):
            out.append({"시도": r["시도"], "시군구": r["시군구"], "순위": rank,
                        "쌍둥이_시도": t["시도"], "쌍둥이_시군구": t["시군구"], "거리": round(dist, 3)})
    write_csv(OUT / "tables" / "twins.csv", out, list(out[0]))
    print(f"{len(rows)}개 단위 (한쪽 자료에만 있는 것: {sorted(only) or '없음'})")
    want = names or [r["시군구"] for r in rows if r["시도"] == "경상북도"]
    for r, tw in zip(rows, twins):
        if r["시군구"] in want and (names or r["시도"] == "경상북도"):
            s = ", ".join(f"{SHORT[t['시도']]} {t['시군구']}({dist:.2f})" for t, dist in tw)
            print(f"{SHORT[r['시도']]} {r['시군구']:<5} 인구 {r['인구']:>9,} 65+ {r['65세이상_비율']:.0%} → {s}")


if __name__ == "__main__":
    main(sys.argv[1:])
