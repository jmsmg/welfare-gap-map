"""공개 저장소에 올리기 전에 받은 자료에서 개인 식별 칸을 지운다 (표준 라이브러리만, 여러 번 돌려도 같다).

지우는 칸 (분석에 쓰지 않는 칸만):
  data/raw/api/provider_BD01.json   email, ownerName(기관장명), telNumber
  data/raw/api/fclt_장애인.json     rprsNm(대표자명)
  data/raw/datagokr/15127872.csv    대표자명, 전화번호
  data/raw/datagokr/15075530.csv    전화번호
기관 이름, 주소, 시군구, 사업 내용 같은 공개 정보와 관공서 부서 연락처는 그대로 둔다.

사용:  python3 -I scripts/scrub_personal.py
"""

import csv
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW

JSON_DROP = {"provider_BD01.json": {"email", "ownerName", "telNumber"}, "fclt_장애인.json": {"rprsNm"}}
CSV_DROP = {"15127872.csv": {"대표자명", "전화번호"}, "15075530.csv": {"전화번호"}}


def scrub_json(path, drop):
    d = json.loads(path.read_text())
    n = 0
    for it in d["items"]:
        for k in list(it):
            if k in drop:
                del it[k]
                n += 1
    d["meta"]["scrubbed"] = sorted(drop)
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    return n


def scrub_csv(path, drop):
    b = path.read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = b.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    rows = list(csv.reader(io.StringIO(text)))
    keep = [i for i, h in enumerate(rows[0]) if h not in drop]
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    for r in rows:
        w.writerow([r[i] for i in keep if i < len(r)])
    path.write_text(out.getvalue(), encoding="utf-8-sig")
    return len(rows[0]) - len(keep)


if __name__ == "__main__":
    for name, drop in JSON_DROP.items():
        p = RAW / "api" / name
        if p.exists():
            print(f"{name}: 값 {scrub_json(p, drop):,}개 지움 ({', '.join(sorted(drop))})")
    for name, drop in CSV_DROP.items():
        p = RAW / "datagokr" / name
        if p.exists():
            print(f"{name}: 칸 {scrub_csv(p, drop)}개 지움 ({', '.join(sorted(drop))})")
