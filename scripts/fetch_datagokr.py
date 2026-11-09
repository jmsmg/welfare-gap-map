"""공공데이터포털 파일데이터를 원본 그대로 받는다 (표준 라이브러리만).

사용:  python3 -I scripts/fetch_datagokr.py <데이터ID> [<데이터ID> ...]
저장:  data/raw/datagokr/<ID>.<확장자> 와 data/raw/datagokr/<ID>.json (제목·수정일·이용허락범위)

브라우저의 «다운로드» 버튼과 같은 순서로 요청한다
(selectFileDataDownload → check-limit → fileDownload). 포털이 다운로드 제한으로
보안문자를 요구하면(needCaptcha) 우회하지 않고 멈춘다. 그 파일은 사용자가 브라우저로 받는다.
"""

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.data.go.kr"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "datagokr"
UA = "competition-analysis/0.1 (python-urllib)"
PAUSE = 2.0  # 요청 사이 쉬는 시간(초)


class NeedsUser(Exception):
    """사람이 브라우저로 받아야 하는 경우."""


def request(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as res:
        out = res.read(), res.headers
    time.sleep(PAUSE)
    return out


def meta_of(page):
    """상세 페이지에서 제목·수정일·이용허락범위·확장자를 뽑는다."""
    text = html.unescape(re.sub(r"(?s)<[^>]+>", "\n", re.sub(r"(?is)<(script|style).*?</\1>", " ", page)))
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    meta = {}
    for i, l in enumerate(lines[:-1]):
        if l in ("파일데이터명", "수정일", "이용허락범위", "확장자", "전체 행", "업데이트 주기", "제공형태") and l not in meta:
            meta[l] = lines[i + 1]
    return meta


def fetch(data_id):
    page = request(f"{BASE}/data/{data_id}/fileData.do")[0].decode("utf-8", "replace")
    meta = meta_of(page)
    if "공공데이터포털에서 다운로드" not in meta.get("제공형태", ""):
        raise NeedsUser(f"{data_id}: 포털에 파일이 없음 ({meta.get('제공형태')})")
    m = re.search(r"fn_fileDataDown\('(\d+)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'", page)
    if not m:
        raise NeedsUser(f"{data_id}: 다운로드 버튼을 못 찾음")
    _, detail_pk, atch, sn = m.groups()

    raw, _ = request(f"{BASE}/tcs/dss/selectFileDataDownload.do", {
        "publicDataDetailPk": detail_pk, "publicDataPk": data_id,
        "atchFileId": atch, "fileDetailSn": sn, "publicDataTyCode": "PR0051",
    })
    info = json.loads(raw)
    if not info.get("status"):
        raise NeedsUser(f"{data_id}: 다운로드 준비 실패 {info.get('error')}")
    atch, sn = info["atchFileId"], info["fileDetailSn"]
    name = info["dataSetFileDetailInfo"].get("dataNm") or meta.get("파일데이터명", data_id)

    raw, _ = request(f"{BASE}/cmm/cmm/check-limit.json", {"atchFileId": atch, "fileDetailSn": sn})
    if json.loads(raw).get("needCaptcha"):
        raise NeedsUser(f"{data_id}: 포털이 보안문자를 요구함 (다운로드 제한)")

    q = urllib.parse.urlencode({"atchFileId": atch, "fileDetailSn": sn, "dataNm": name})
    body, headers = request(f"{BASE}/cmm/cmm/fileDownload.do?{q}")
    if body[:15].lstrip().lower().startswith((b"<!doctype", b"<html")):
        raise NeedsUser(f"{data_id}: 파일 대신 웹페이지가 옴")

    ext = (meta.get("확장자") or "csv").lower().split()[0]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{data_id}.{ext}").write_bytes(body)
    meta.update({"id": data_id, "url": f"{BASE}/data/{data_id}/fileData.do",
                 "fetched": time.strftime("%Y-%m-%d"), "bytes": len(body), "dataNm": name})
    (OUT / f"{data_id}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


def main(ids):
    for data_id in ids:
        try:
            meta = fetch(data_id)
            print(f"✔ {data_id} {meta['bytes']:>9,}B  {meta.get('파일데이터명')}  (수정 {meta.get('수정일')}, {meta.get('이용허락범위')})")
        except NeedsUser as e:
            print(f"✋ {e}")
            if "보안문자" in str(e):
                break


if __name__ == "__main__":
    main(sys.argv[1:])
