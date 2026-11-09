"""분석 스크립트가 같이 쓰는 읽기 함수. 원본 CSV 는 data/raw/ 에 받은 그대로 둔다."""

import csv
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "out"


def read_csv(path):
    """UTF-8(BOM 포함) 이나 CP949 CSV 를 dict 행 목록으로 읽는다."""
    b = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = b.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return list(csv.DictReader(io.StringIO(text)))


def num(s):
    s = (s or "").replace(",", "").strip()
    return int(float(s)) if s else 0


def sigungu(name):
    """'경상북도 포항시', '포항시 남구', '포항시남구' 를 모두 '포항시' 로 맞춘다 (일반구는 시로 묶는다)."""
    name = name.strip()
    for sido in ("경상북도", "경북"):
        if name.startswith(sido + " "):
            name = name[len(sido) + 1:]
    name = name.replace(" ", "")
    if "시" in name and name.endswith("구") and not name.endswith("시"):
        name = name[: name.index("시") + 1]
    return name


# 시군구 맞춤 규칙 (전국 자료끼리 잇는 열쇠)
SHORT = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주",
         "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원",
         "충청북도": "충북", "충청남도": "충남", "전북특별자치도": "전북", "전라남도": "전남", "경상북도": "경북",
         "경상남도": "경남", "제주특별자치도": "제주"}
LONG = {v: k for k, v in SHORT.items()}
SIDO_ALIAS = {"강원도": "강원특별자치도", "전라북도": "전북특별자치도"}  # 옛 이름으로 적힌 자료
GWANGJU_GU = {"동구", "서구", "남구", "북구", "광산구"}
# 인천 2026-07 개편: 중구, 동구, 서구 에서 제물포구, 영종구, 서해구, 검단구. 2025-12 수급 자료와 맞추려고 한 단위로 묶는다
INCHEON_OLD_NEW = {"중구", "동구", "서구", "제물포구", "영종구", "서해구", "검단구"}
INCHEON_UNIT = "중구·동구·서구(개편 전 범위)"  # 분석용 이름. 제출물에는 쓰지 않는다


def sido_name(s):
    s = s.strip()
    return SIDO_ALIAS.get(s, LONG.get(s, s))


def unit(sido, sgg):
    """(시도, 시군구) 를 분석 단위로 맞춘다: 일반구는 시로, 세종은 하나로, 광주 전남 통합과 인천 개편은 2025-12 기준으로."""
    sido, sgg = sido_name(sido), sgg.strip()
    if sido == "전남광주통합특별시":
        sido = "광주광역시" if sgg in GWANGJU_GU else "전라남도"
    if sido == "세종특별자치시":
        return (sido, sido)
    if sido == "인천광역시" and sgg in INCHEON_OLD_NEW:
        return (sido, INCHEON_UNIT)
    return (sido, sigungu(sgg))


def write_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
