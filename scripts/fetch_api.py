"""오픈API 로 사회서비스 제공기관과 사회복지시설 목록을 받는다. 받은 것은 data/raw/api/ 에 그대로 둔다.

사용:
  python3 -I scripts/fetch_api.py check
      키가 세 API 에 다 듣는지 한 번씩만 불러 본다 (지자체복지서비스, 사회복지시설, 사회서비스 제공기관)
  python3 -I scripts/fetch_api.py provider [--type BD01]
      사업구분이 그 코드인 사회서비스 제공기관 전체 → data/raw/api/provider_BD01.json
  python3 -I scripts/fetch_api.py fclt-kinds
      사회복지시설 종류 코드 → data/raw/api/fclt_kinds.json
  python3 -I scripts/fetch_api.py fclt --word 장애인
      종류 이름에 그 말이 든 사회복지시설 목록 전체 → data/raw/api/fclt_장애인.json (fclt-kinds 다음에)

자료:
  사회서비스 제공기관: 한국사회보장정보원_사회서비스 제공기관 정보 검색 (data.go.kr 15057683, 사회서비스 전자바우처).
      서버는 api.socialservice.or.kr:444, 개발계정 하루 100회. 한 번에 1,000행까지 받는다.
      사업구분 BD01 은 발달장애인지원이고 사업유형(serviceName)이 셋이다: 발달장애인 주간활동서비스,
      청소년 발달장애인 방과후활동서비스, 최중증발달장애인 통합돌봄서비스.
      (사업구분 코드는 같은 서버의 공통코드 조회에서 확인, 2026-11-08. 사업구분명 serviceTypeName 으로는 걸러지지 않는다)
      이 서버는 2026-11-08 에 키 없이도 답했다. 키가 .env 에 있으면 붙여 보낸다.
  사회복지시설: 한국사회보장정보원_사회복지시설정보서비스 현황 (data.go.kr 15001848), apis.data.go.kr 게이트웨이.
      키가 있어야 하고, 하루 10,000회. 명세의 numOfRows 가 두 자리라 한 번에 99행씩 받는다.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import api

OUT = api.ROOT / "data" / "raw" / "api"
LCGV = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations"
FCLT = "https://apis.data.go.kr/B554287/sclWlfrFcltInfoInqirService2"
PROV = "https://api.socialservice.or.kr:444/api/service/provider/providerList"
FCLT_ROWS = 99
PROV_ROWS = 1000


def pages(url, rows, key_param="serviceKey", key_required=True, **params):
    """모든 쪽을 돌며 item 을 모은다. (items, totalCount)"""
    items, page, total = [], 1, None
    while total is None or len(items) < total:
        try:
            _, root = api.call(url, {"pageNo": page, "numOfRows": rows, **params}, key_param, key_required)
        except api.ApiError as e:
            if e.empty:  # 조건에 맞는 자료가 없음
                return items, total or 0
            raise
        total = int((root.findtext(".//totalCount") or "0").strip() or 0)
        got = [api.leaf(el) for el in root.iter("item")]
        if not got:
            break
        items += got
        print(f"  {page} 쪽: {len(items):,}/{total:,}")
        page += 1
    return items, total


def save(name, source, params, items, total):
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"fetched": time.strftime("%Y-%m-%d"), "source": source, "params": params,
            "totalCount": total, "got": len(items)}
    (OUT / name).write_text(json.dumps({"meta": meta, "items": items}, ensure_ascii=False, indent=1))
    print(f"✔ {len(items):,}/{total:,}건 → data/raw/api/{name}")


def cmd_check(_):
    tests = [
        ("지자체복지서비스 15108347", f"{LCGV}/LcgvWelfarelist", "serviceKey"),
        ("사회복지시설 15001848", f"{FCLT}/getFcltKindCodeInfoInqire2", "serviceKey"),
        ("사회서비스 제공기관 15057683", PROV, "ServiceKey"),
    ]
    for name, url, kp in tests:
        try:
            _, root = api.call(url, {"pageNo": 1, "numOfRows": 1}, kp)
            print(f"✔ {name}: 통과 (전체 {root.findtext('.//totalCount')}건)")
        except api.ApiError as e:
            print(f"✋ {name}: {e}")


def cmd_provider(a):
    items, total = pages(PROV, PROV_ROWS, "ServiceKey", False, serviceType=a.type)
    save(f"provider_{a.type}.json", PROV, {"serviceType": a.type}, items, total)


def cmd_fclt_kinds(_):
    url = f"{FCLT}/getFcltKindCodeInfoInqire2"
    items, total = pages(url, FCLT_ROWS)
    save("fclt_kinds.json", url, {}, items, total)
    for k in items:
        print(" ", k.get("fcltKindCd"), k.get("fcltKindNm"), "|", k.get("fcltDtlKindNm"), "|", k.get("fcltUseRcpnNm"))


def cmd_fclt(a):
    kinds = json.loads((OUT / "fclt_kinds.json").read_text())["items"]
    text = lambda k: " ".join(k.get(f, "") for f in ("fcltKindNm", "fcltDtlKindNm", "fcltUseRcpnNm"))
    codes = sorted({k["fcltKindCd"] for k in kinds if a.word in text(k)})
    print(f"  '{a.word}' 이 든 시설 종류 {len(codes)}개")
    url = f"{FCLT}/getFcltListInfoInqire2"
    out = []
    for cd in codes:
        items, total = pages(url, FCLT_ROWS, fcltKindCd=cd)
        print(f"  {cd}: {total:,}곳")
        out += items
    save(f"fclt_{a.word}.json", url, {"fcltKindCd": codes}, out, len(out))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    pp = sub.add_parser("provider")
    pp.add_argument("--type", default="BD01")
    sub.add_parser("fclt-kinds")
    fp = sub.add_parser("fclt")
    fp.add_argument("--word", default="장애인")
    a = p.parse_args()
    try:
        {"check": cmd_check, "provider": cmd_provider, "fclt-kinds": cmd_fclt_kinds, "fclt": cmd_fclt}[a.cmd](a)
    except api.ApiError as e:
        sys.exit(f"✋ {e} (여기서 멈춤)")


if __name__ == "__main__":
    main()
