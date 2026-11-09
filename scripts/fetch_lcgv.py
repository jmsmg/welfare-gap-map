"""지자체복지서비스 오픈API(한국사회보장정보원, data.go.kr 15108347)를 받는다.

사용:
  python3 -I scripts/fetch_lcgv.py list                          전국 목록 전체 → data/raw/api/lcgv_list.json
  python3 -I scripts/fetch_lcgv.py detail --sido 경상북도 --word 장애   목록에서 골라 상세 → data/raw/api/lcgv_detail/<servId>.xml

키는 .env 의 DATA_GO_KR_KEY (공공데이터포털 일반 인증키, Decoding). 키는 화면에 찍지 않는다.
개발계정은 하루 1,000회라 상세는 필요한 것만, 받은 것은 다시 받지 않는다.
한도·권한 오류가 오면 거기서 멈춘다.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import api

API = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations"
OUT = api.ROOT / "data" / "raw" / "api"


def call(op, **params):
    return api.call(f"{API}/{op}", params)


row = api.leaf


def cmd_list(_):
    items, page, total = [], 1, None
    while total is None or len(items) < total:
        _, root = call("LcgvWelfarelist", pageNo=page, numOfRows=500)
        total = int(root.findtext(".//totalCount") or 0)
        got = [row(el) for el in root.iter("servList")]
        if not got:
            break
        items += got
        print(f"  {page} 쪽: {len(items):,}/{total:,}")
        page += 1
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"fetched": time.strftime("%Y-%m-%d"), "source": f"{API}/LcgvWelfarelist", "totalCount": total}
    (OUT / "lcgv_list.json").write_text(json.dumps({"meta": meta, "items": items}, ensure_ascii=False, indent=1))
    print(f"✔ 목록 {len(items):,}건 → data/raw/api/lcgv_list.json")


def cmd_detail(a):
    items = json.loads((OUT / "lcgv_list.json").read_text())["items"]
    pick = [i for i in items
            if (not a.sido or i.get("ctpvNm") == a.sido)
            and (not a.word or any(a.word in (i.get(f) or "") for f in ("servNm", "servDgst", "trgterIndvdlNmArray")))]
    d = OUT / "lcgv_detail"
    d.mkdir(parents=True, exist_ok=True)
    todo = [i for i in pick if not (d / f"{i['servId']}.xml").exists()][: a.limit]
    print(f"  고른 것 {len(pick):,}건, 이번에 받을 것 {len(todo):,}건")
    for n, i in enumerate(todo, 1):
        try:
            body, _ = call("LcgvWelfaredetailed", servId=i["servId"])
        except api.ApiError as e:
            print(f"✋ {i['servId']} {e}")
            if e.stop:
                print(f"  {n - 1}건 받고 멈춤")
                return
            continue
        (d / f"{i['servId']}.xml").write_bytes(body)
        if n % 50 == 0:
            print(f"  {n:,}건")
    print(f"✔ 상세 {len(todo):,}건 → data/raw/api/lcgv_detail/")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    dp = sub.add_parser("detail")
    dp.add_argument("--sido")
    dp.add_argument("--word")
    dp.add_argument("--limit", type=int, default=800)
    a = p.parse_args()
    try:
        {"list": cmd_list, "detail": cmd_detail}[a.cmd](a)
    except api.ApiError as e:
        sys.exit(f"✋ {e} (여기서 멈춤)")


if __name__ == "__main__":
    main()
