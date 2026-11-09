"""시범 분석 1: 경북 시군의 발달장애인 수 대비 주간활동, 방과후활동 제공기관.

수요: 복지로 사회보장통계 '장애인등록 장애유형별 연령별 장애인수' (2026-09, bokjiro.py) 의 지적 + 자폐성 장애인.
      나눌 수는 서비스 나이대 6~64세 (주간활동 18~64세, 청소년 방과후활동 6~17세). 65세 이상은 주간활동 대상에서
      빠지는 때가 있어 보수적으로 뺀다 (bokjiro.py 머리글).
      경상북도_장애인 등록 현황 (2026-02-28, 15063014) 의 발달장애인 수는 견주기용으로 같이 적는다.
공급: 발달장애인 주간활동, 방과후활동 제공기관. 사회서비스 전자바우처에 지금 등록된 기관
      (사회서비스 제공기관 정보 검색 API, 2026-11-08 조회. providers.py)
      옛 파일 2025-09 (한국장애인개발원), 2024-04 (한국사회보장정보원) 의 수는 견주기용으로 같이 적는다
      장애인 주간보호시설 수 (참고): 사회복지시설정보서비스 API 의 장애인주간이용시설 (2026-11-08 조회).
      보건복지부_장애인 주간이용시설현황 (2024-04-25) 의 시설 수와 정원도 견주기용으로 적는다
인구: 행정안전부_지역별(행정동) 성별 연령별 주민등록 인구수 (2026-10-31)

사용:  python3 -I scripts/gb_dev_gap.py
결과:  out/tables/gb_dev_gap.csv
"""

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I 로 돌려도 같은 폴더의 모듈을 쓴다
import bokjiro
import providers
from common import OUT, RAW, num, read_csv, sigungu, write_csv

SIDO = "경상북도"
DEV = ("지적", "자폐성")


def population():
    pop = collections.Counter()
    for r in read_csv(RAW / "datagokr" / "15097972.csv"):
        if r["시도명"] == SIDO and r["시군구명"].strip():
            pop[sigungu(r["시군구명"])] += num(r["계"])
    return pop


def gb_file():
    """경상북도 장애인 등록 현황 (2026-02): 시군별 발달장애인 (견주기용)."""
    dev = collections.Counter()
    for r in read_csv(RAW / "datagokr" / "15063014.csv"):
        if r["유형"] in DEV:
            dev[sigungu(r["시군구"])] += sum(num(v) for k, v in r.items() if k not in ("시군구", "유형"))
    return dev


def per(n, d):
    return round(n / d, 1) if d else ""


def main():
    pop, old_dev = population(), gb_file()
    dem, sup, care = bokjiro.counts(), providers.counts(), providers.daycare()
    rows = []
    for u in sorted(u for u in dem if u[0] == SIDO):
        g = u[1]
        d, s, c = dem[u], sup[u], care[u]
        rows.append({
            "시군": g,
            "인구": pop[g],
            "등록장애인": d["등록장애인"],
            "발달장애인": d["발달장애인"],
            "발달장애인_6_64": d["발달_6_64"],
            "발달장애인_18_64": d["발달_18_64"],
            "발달장애인_6_17": d["발달_6_17"],
            "발달장애인_인구천명당": round(d["발달장애인"] / pop[g] * 1000, 2),
            "주간활동_기관": s["주간활동"],
            "방과후_기관": s["방과후"],
            "제공기관": s["제공기관"],
            "발달장애인_기관당": per(d["발달_6_64"], s["제공기관"]),
            "주간활동_기관당_18_64": per(d["발달_18_64"], s["주간활동"]),
            "방과후_기관당_6_17": per(d["발달_6_17"], s["방과후"]),
            "통합돌봄만_기관": s["통합돌봄만_2026-11"],
            "제공기관_2025-09": s["제공기관_2025-09"],
            "제공기관_2024-04": s["제공기관_2024-04"],
            "발달장애인_경북파일_2026-02": old_dev[g],
            "주간보호_시설": c["주간보호_시설"],
            "주간보호_시설_2024-04": c["주간보호_시설_2024-04"],
            "주간보호_정원_2024-04": c["주간보호_정원_2024-04"],
        })
    rows.sort(key=lambda r: (r["제공기관"] > 0, -(r["발달장애인_6_64"] / max(r["제공기관"], 1))))
    fields = list(rows[0])
    write_csv(OUT / "tables" / "gb_dev_gap.csv", rows, fields)

    tot_dev, tot_svc = sum(r["발달장애인"] for r in rows), sum(r["발달장애인_6_64"] for r in rows)
    tot_org = sum(r["제공기관"] for r in rows)
    has = [r for r in rows if r["제공기관"]]
    lo, hi = min(has, key=lambda r: r["발달장애인_기관당"]), max(has, key=lambda r: r["발달장애인_기관당"])
    none = [r["시군"] for r in rows if not r["제공기관"]]
    print(f"쓴 자료: 수요 복지로 {bokjiro.MONTH}, 공급 {sorted({s['쓴_자료'] for s in sup.values() if s['쓴_자료']})}")
    print(f"경북 {len(rows)}개 시군, 발달장애인 {tot_dev:,}명 (6~64세 {tot_svc:,}명, 경북 2026-02 파일 {sum(old_dev.values()):,}명), "
          f"제공기관 {tot_org}곳 (6~64세 기관당 {tot_svc / tot_org:.1f}명)")
    print(f"기관당 발달장애인(6~64세): {lo['시군']} {lo['발달장애인_기관당']}명 ~ {hi['시군']} {hi['발달장애인_기관당']}명 "
          f"({hi['발달장애인_기관당'] / lo['발달장애인_기관당']:.1f}배), 기관 없음: {', '.join(none)}")
    print(" | ".join(fields))
    for r in rows:
        print(" | ".join(str(r[f]) for f in fields))
    diff = [f"{r['시군']} {r['제공기관']}곳 (옛 파일 {r['제공기관_2025-09']}, {r['제공기관_2024-04']})" for r in rows
            if r["제공기관"] != max(r["제공기관_2025-09"], r["제공기관_2024-04"])]
    print("지금(2026-11) 과 옛 파일(2025-09, 2024-04 가운데 많은 쪽) 의 기관 수가 다른 시군:", ", ".join(diff) or "없음")
    old_tot = sum(max(r["제공기관_2025-09"], r["제공기관_2024-04"]) for r in rows)
    print(f"옛 파일로 셌다면: 제공기관 {old_tot}곳 (6~64세 기관당 {tot_svc / old_tot:.1f}명)")


if __name__ == "__main__":
    main()
