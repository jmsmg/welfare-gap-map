"""복지로 사회보장통계 '장애인등록 장애유형별 연령별 장애인수' (datsNo=26) 를 분석 단위별로 센다.

자료: data/raw/bokjiro/datsNo26_<연월>/PDQCSV_26_*.csv (2026-11-08 복지로에서 받음, 통계연월 2026-09, 전국 시군구,
      한 행이 시군구 x 나이(0~124세) x 장애유형 16종). 원본은 한국사회보장정보원, 공공누리 1유형.
발달장애인 = 장애유형이 지적, 자폐성인 사람 (발달장애인법 제2조).
나이대 (2026-11-08 기준 사업 대상):
  주간활동서비스: 만 18세 이상 65세 미만 → 18~64세
  청소년 방과후활동서비스: 만 6세 이상 18세 미만 → 6~17세
  둘을 합친 서비스 나이대: 6~64세

사용:  python3 -I scripts/bokjiro.py      (전국, 경북 요약을 찍는다)
"""

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW, read_csv, unit

MONTH = "202609"
DEV = ("지적", "자폐성")
DAY = (18, 64)       # 주간활동
AFTER = (6, 17)      # 청소년 방과후활동
SERVICE = (6, 64)    # 둘을 합친 나이대


def path():
    d = RAW / "bokjiro" / f"datsNo26_{MONTH}"
    files = sorted(d.glob("PDQCSV_26_*.csv"))
    if not files:
        sys.exit(f"복지로 파일이 없다: {d}/PDQCSV_26_*.csv (README 의 '복지로 26' 참고)")
    return files[0]


def counts():
    """단위별 Counter: 등록장애인, 발달장애인, 발달_6_64, 발달_18_64, 발달_6_17."""
    c = collections.defaultdict(collections.Counter)
    for r in read_csv(path()):
        u = unit(r["통계시도명"], r["통계시군구명"])
        n, age = int(r["등록장애인수"]), int(r["연령"])
        x = c[u]
        x["등록장애인"] += n
        if r["장애유형"] in DEV:
            x["발달장애인"] += n
            if SERVICE[0] <= age <= SERVICE[1]:
                x["발달_6_64"] += n
            if DAY[0] <= age <= DAY[1]:
                x["발달_18_64"] += n
            if AFTER[0] <= age <= AFTER[1]:
                x["발달_6_17"] += n
    return c


if __name__ == "__main__":
    c = counts()
    keys = ("등록장애인", "발달장애인", "발달_6_64", "발달_18_64", "발달_6_17")
    tot = collections.Counter()
    for x in c.values():
        tot.update(x)
    print(f"{path().name} (통계연월 {MONTH}), {len(c)}개 단위")
    print("전국:", ", ".join(f"{k} {tot[k]:,}" for k in keys))
    gb = collections.Counter()
    for u, x in c.items():
        if u[0] == "경상북도":
            gb.update(x)
    print("경북:", ", ".join(f"{k} {gb[k]:,}" for k in keys))
    print("시군 | " + " | ".join(keys))
    for u in sorted(u for u in c if u[0] == "경상북도"):
        print(u[1], "|", " | ".join(f"{c[u][k]:,}" for k in keys))
