"""발달장애인 주간활동, 청소년 방과후활동 제공기관을 분석 단위(시군구)별로 센다.

쓰는 값은 사회서비스 전자바우처에 지금 등록된 기관이다:
  2026-11: 한국사회보장정보원_사회서비스 제공기관 정보 검색 API (data.go.kr 15057683), 사업구분 BD01 발달장애인지원,
           2026-11-08 조회 (scripts/fetch_api.py provider). 기관마다 아이디가 있어 이름으로 짝지을 일이 없다.
           한 기관이 여러 시군구에 등록돼 있으면 시군구마다 센다 (등록된 시군구가 그 기관이 서비스하는 곳이다).
           최중증발달장애인 통합돌봄만 하는 기관은 따로 세고 제공기관에 넣지 않는다.
API 자료가 없으면 옛 파일 두 가지를 같은 규칙으로 따로 정리하고, 단위마다 기관이 더 많이 실린 쪽 수를 쓴다.
옛 파일은 비교용으로 늘 같이 센다 (파일이 1년 묵으면 공백 판단이 어떻게 틀리는지 보이려고).
  2025-09: 한국장애인개발원_발달장애인 지원 기관 및 제공서비스 (data.go.kr 15072489). 한 행이 기관 하나, 서비스마다 O/X.
  2024-04: 한국사회보장정보원_발달장애인지원사업 제공기관 정보 (data.go.kr 15127872). 한 행이 기관과 사업 하나.
옛 두 파일을 이름으로 합치지 않는 까닭: 같은 기관도 자료마다 이름이 달라서(예: '경북어울림사회적협동조합' 과
'사회적협동조합경북어울림') 이름이 같은 것만 합치면 같은 기관을 두 번 센다. 이 짝짓기가 AI 1단계(LLM 정리)가 할 일이다.

정리 규칙 (README 의 '제공기관 정리 규칙' 과 같다):
  1. 관공서(시청, 군청, 구청, 도청, 행정복지센터, 주민센터) 행은 뺀다. 지자체 담당 부서가 올라 있는 행이라 제공기관이 아니다.
     '시청소년' 처럼 이름 안에 '청소년' 이 든 기관은 남긴다.
  2. 시군구 칸에 주소가 들어간 행은 시도와 시군구(일반구는 시)까지만 쓴다.
  3. 시도만 적힌 행은 기관 이름에 든 시군구 이름(예: '경산시지부')으로 시군구를 정한다. 하나로 정해지지 않으면 뺀다.
  4. 한 자료 안에서, 같은 단위에 이름이 같은 기관(법인 표기, 띄어쓰기, 시도 긴 이름과 짧은 이름, 지적장애인복지협회의
     옛 이름 차이를 지운 뒤)은 하나로 합치고 서비스는 합친다.

사용:  python3 -I scripts/providers.py     (정리 결과 요약을 찍는다)
"""

import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW, SHORT, num, read_csv, sido_name, unit

SOURCES = ("2025-09", "2024-04")  # 옛 파일
LIVE = "2026-11"  # 전자바우처 API
LIVE_FILE = RAW / "api" / "provider_BD01.json"
LIVE_KIND = {"발달장애인 주간활동서비스": "주간", "청소년 발달장애인 방과후활동서비스": "방과후",
             "최중증발달장애인 통합돌봄서비스": "통합돌봄"}
GOV = re.compile(r"(시|군|구|도)청(?!소년)|행정복지센터|주민센터")
LEGAL = re.compile(r"\((사|재|주|복)\)|㈜|^(사|재)\)|사단법인|재단법인|사회복지법인|주식회사")


def norm_name(name):
    s = LEGAL.sub("", name)
    for long, short in SHORT.items():
        s = s.replace(long, short)
    s = s.replace("지적장애인복지협회", "지적발달장애인복지협회")  # 협회의 옛 이름 (같은 단체)
    return re.sub(r"[\s()·.,]", "", s)


def known_units():
    """주민등록 인구 자료에 있는 분석 단위 (시도별 시군구 이름)."""
    by_sido = collections.defaultdict(set)
    for r in read_csv(RAW / "datagokr" / "15097972.csv"):
        if r["시군구명"].strip():
            s, g = unit(r["시도명"], r["시군구명"])
            by_sido[s].add(g)
    return by_sido


def place(field, name, units):
    """시군구 칸(주소가 섞이기도 한다)과 기관 이름에서 분석 단위를 정한다. 못 정하면 (None, 까닭)."""
    toks = field.split()
    sido = sido_name(toks[0])
    sgg = []
    for t in toks[1:3]:
        if not re.search(r"(시|군|구)$", t):
            break
        sgg.append(t)
    if sgg:
        return unit(sido, " ".join(sgg)), None
    if sido == "세종특별자치시":
        return unit(sido, ""), None
    hits = {g for g in units.get(sido, ()) if g in name}
    if len(hits) == 1:
        return (sido, hits.pop()), None
    return None, f"시도만 적혀 있고 이름으로 시군구를 못 정함: {field} | {name}"


def raw_rows():
    """두 자료를 (자료, 시군구 칸, 기관 이름, 주간활동, 방과후) 로 맞춰 내놓는다."""
    for r in read_csv(RAW / "datagokr" / "15072489.csv"):
        day, after = r["주간활동"] == "O", r["청소년방과후활동"] == "O"
        if day or after:
            yield "2025-09", r["시군구명"], r["수행기관명"].strip(), day, after
    for r in read_csv(RAW / "datagokr" / "15127872.csv"):
        kind = r["사업유형"]
        yield "2024-04", r["시군구"], r["제공기관_명"].strip(), "주간활동" in kind, "방과후" in kind


def load():
    """자료별로 정리한 기관 목록과 정리 기록. 기관: {자료: {단위: {정규화 이름: {이름, 주간, 방과후, 행}}}}"""
    units = known_units()
    orgs = {src: collections.defaultdict(dict) for src in SOURCES}
    log = collections.Counter()
    dropped = []
    for src, field, name, day, after in raw_rows():
        log[f"{src} 행"] += 1
        if GOV.search(name):
            log[f"{src} 관공서 행 뺌"] += 1
            dropped.append(f"{src} 관공서: {field} | {name}")
            continue
        u, why = place(field, name, units)
        if u is None:
            log[f"{src} 단위 못 정해 뺌"] += 1
            dropped.append(f"{src} {why}")
            continue
        o = orgs[src][u].setdefault(norm_name(name), {"이름": name, "주간": False, "방과후": False, "행": 0})
        if o["행"]:
            log[f"{src} 같은 기관 합침"] += 1
        o["주간"] |= day
        o["방과후"] |= after
        o["행"] += 1
    return orgs, log, dropped


def live():
    """API 자료를 단위별 {주간, 방과후, 통합돌봄: 기관 아이디 집합} 으로. 파일이 없으면 None."""
    if not LIVE_FILE.exists():
        return None
    by_unit = collections.defaultdict(lambda: collections.defaultdict(set))
    for i in json.loads(LIVE_FILE.read_text())["items"]:
        kind = LIVE_KIND.get(i["serviceName"])
        if kind is None:
            raise ValueError(f"모르는 사업유형: {i['serviceName']} (LIVE_KIND 에 넣을 것)")
        sido = i["sidoName"]
        by_unit[unit(sido, i["signguName"][len(sido):])][kind].add(i["providerId"])
    return by_unit


def counts():
    """단위별 Counter.
    제공기관_<자료>, 주간활동_<자료>, 방과후_<자료>: 자료별 수 (둘 중 하나라도 하는 기관은 제공기관에 한 번만)
    통합돌봄만_2026-11: 최중증 통합돌봄만 하는 기관 (제공기관에 넣지 않는다)
    제공기관, 주간활동, 방과후: 쓰는 값. API 자료가 있으면 그것, 없으면 옛 두 파일 가운데 많은 쪽 (같으면 새 파일)"""
    orgs, _, _ = load()
    c = collections.defaultdict(collections.Counter)
    for src, by_unit in orgs.items():
        for u, d in by_unit.items():
            for o in d.values():
                c[u][f"주간활동_{src}"] += o["주간"]
                c[u][f"방과후_{src}"] += o["방과후"]
                c[u][f"제공기관_{src}"] += 1
    now = live()
    for u, k in (now or {}).items():
        dp = k["주간"] | k["방과후"]
        c[u][f"주간활동_{LIVE}"] = len(k["주간"])
        c[u][f"방과후_{LIVE}"] = len(k["방과후"])
        c[u][f"제공기관_{LIVE}"] = len(dp)
        c[u][f"통합돌봄만_{LIVE}"] = len(k["통합돌봄"] - dp)
    for u, x in c.items():
        best = LIVE if now is not None else max(SOURCES, key=lambda s: x[f"제공기관_{s}"])
        for k in ("제공기관", "주간활동", "방과후"):
            x[k] = x[f"{k}_{best}"]
        x["쓴_자료"] = best
    return c


FCLT_FILE = RAW / "api" / "fclt_장애인.json"
DAYCARE_KIND = "030203"  # 사회복지시설 종류 코드: 장애인지역사회재활시설 > 장애인주간이용시설


def facilities(kind=DAYCARE_KIND):
    """사회복지시설정보서비스 API (data.go.kr 15001848, fetch_api.py fclt) 에서 그 종류의 시설을 단위별로 센다.
    소관 시군구가 시도 이름뿐인 시설(시도가 맡는 시설)은 단위를 못 정해 빼고 그 수를 따로 돌려준다. 파일이 없으면 None."""
    if not FCLT_FILE.exists():
        return None, 0
    c, skipped = collections.Counter(), 0
    for i in json.loads(FCLT_FILE.read_text())["items"]:
        if i.get("fcltKindCd") != kind:
            continue
        sido, _, sgg = (i.get("jrsdSggNm") or "").strip().partition(" ")
        if not sgg and sido != "세종특별자치시":
            skipped += 1
            continue
        c[unit(sido, sgg)] += 1
    return c, skipped


def daycare():
    """장애인 주간보호시설, 단위별.
    주간보호_시설: 사회복지시설정보서비스 API 의 장애인주간이용시설 수 (2026-11-08 조회). API 파일이 없으면 2024-04 값.
    주간보호_시설_2024-04, 주간보호_정원_2024-04: 보건복지부_장애인 주간이용시설현황 (data.go.kr 15075530, 2024-04-25)."""
    c = collections.defaultdict(collections.Counter)
    for r in read_csv(RAW / "datagokr" / "15075530.csv"):
        u = unit(r["시도"], r["시군구"])
        c[u]["주간보호_시설_2024-04"] += 1
        c[u]["주간보호_정원_2024-04"] += num(r["이용자 정원"])
    now, _ = facilities()
    for u in set(c) | set(now or ()):
        c[u]["주간보호_시설"] = now[u] if now is not None else c[u]["주간보호_시설_2024-04"]
    return c


if __name__ == "__main__":
    orgs, log, dropped = load()
    for k, v in sorted(log.items()):
        print(f"{k}: {v:,}")
    c = counts()
    for src in SOURCES:
        print(f"{src}: 정리 뒤 제공기관 {sum(len(d) for d in orgs[src].values()):,}곳, {len(orgs[src])}개 단위")
    now = live()
    if now is not None:
        ids = set().union(*(k["주간"] | k["방과후"] for k in now.values()))
        print(f"{LIVE} (API): 주간활동, 방과후 제공기관 {len(ids):,}곳, 시군구 등록 {sum(x[f'제공기관_{LIVE}'] for x in c.values()):,}건, "
              f"{sum(1 for x in c.values() if x[f'제공기관_{LIVE}']):,}개 단위")
        old = {u: max(x[f"제공기관_{s}"] for s in SOURCES) for u, x in c.items()}
        more = sum(1 for u, x in c.items() if x[f"제공기관_{LIVE}"] > old[u])
        less = sum(1 for u, x in c.items() if x[f"제공기관_{LIVE}"] < old[u])
        print(f"옛 파일(많은 쪽)과 견주면: API 가 많은 단위 {more}, 적은 단위 {less}, 같은 단위 {len(c) - more - less}")
    day, skipped = facilities()
    if day is not None:
        print(f"장애인주간이용시설 (사회복지시설 API): {sum(day.values()):,}곳, {len(day)}개 단위, 시도 소관이라 뺀 시설 {skipped}곳")
    print(f"쓰는 값: 제공기관 {sum(x['제공기관'] for x in c.values()):,}곳(시군구 등록 기준), {len(c)}개 단위, "
          f"자료 {sorted(set(x['쓴_자료'] for x in c.values()))}")
    for d in dropped:
        print("  뺌 -", d)
