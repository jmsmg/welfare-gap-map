"""공공데이터포털 오픈API 를 부르는 공통 함수 (표준 라이브러리만).

키는 .env 의 DATA_GO_KR_KEY (공공데이터포털 일반 인증키, Decoding). 키는 화면에도 파일에도 남기지 않는다.
오류 응답은 ApiError 로 올린다. 한도, 권한, 키 오류면 err.stop 이 참이고, 부르는 쪽이 거기서 멈춘다.
"""

import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "competition-analysis/0.1 (python-urllib)"
PAUSE = 1.0  # 요청 사이 쉬는 시간(초)
# 포털 오류코드: 20 접근 거부, 22 하루 한도 넘음, 30 등록 안 된 키, 31 기한 끝남, 32 등록 안 된 IP, 33 서명 안 됨
STOP_CODES = {"20", "22", "30", "31", "32", "33"}
NO_DATA_CODES = {"03", "40"}  # 조건에 맞는 자료가 없음 (포털 표준 03, 사회복지시설 API 는 40 NO DATA FOUND)


class ApiError(RuntimeError):
    def __init__(self, code, msg):
        super().__init__(f"오류 {code} {msg}".strip())
        self.code = code
        self.stop = code in STOP_CODES
        self.empty = code in NO_DATA_CODES


def key(required=True):
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("DATA_GO_KR_KEY="):
                k = line.split("=", 1)[1].strip()
                if k:
                    # Encoding 키(%2B 같은 것이 든 것)를 넣어도 된다. 풀어서 Decoding 키로 쓰고, 보낼 때 한 번만 인코딩한다
                    return urllib.parse.unquote(k) if "%" in k else k
    if required:
        sys.exit(".env 의 DATA_GO_KR_KEY 가 비어 있다 (공공데이터포털 마이페이지의 일반 인증키, Decoding)")
    return None


def scrub(text, k):
    """오류 글에 키가 섞여 나오면 지운다."""
    if k:
        for v in (k, urllib.parse.quote(k, safe=""), urllib.parse.quote_plus(k)):
            text = text.replace(v, "***")
    return text


def call(url, params, key_param="serviceKey", key_required=True):
    """GET 으로 부르고 XML 응답을 (본문 bytes, 루트) 로 돌려준다.
    key_required=False 면 키가 없을 때 키 없이 부른다 (키를 확인하지 않는 서버용)."""
    k = key(key_required)
    q = urllib.parse.urlencode({**({key_param: k} if k else {}), **params})
    req = urllib.request.Request(f"{url}?{q}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            body = res.read()
    except urllib.error.HTTPError as e:  # 게이트웨이는 오류도 XML 로 준다
        body = e.read()
    finally:
        time.sleep(PAUSE)
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise ApiError("응답", scrub(body[:200].decode("utf-8", "replace"), k)) from None
    code = (root.findtext(".//resultCode") or root.findtext(".//returnReasonCode") or "").strip()
    if code and code not in ("0", "00"):
        msg = " ".join(filter(None, (root.findtext(".//resultMsg"), root.findtext(".//resultMessage"),
                                     root.findtext(".//errMsg"), root.findtext(".//returnAuthMsg"))))
        raise ApiError(code, scrub(msg.strip(), k))
    return body, root


def leaf(el):
    """XML 요소의 맨 끝 자식들을 dict 로."""
    return {c.tag.strip(): (c.text or "").strip() for c in el if len(c) == 0}
