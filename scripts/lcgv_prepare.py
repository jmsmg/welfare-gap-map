"""LLM 사업 정리 시범(AI 1단계)의 입력을 만든다.

지자체복지서비스 상세(data/raw/api/lcgv_detail/*.xml, fetch_lcgv.py)에서
  LLM 에게 줄 글: 사업명, 요약, 지원 대상, 선정 기준, 지원 내용 → out/llm/input_<n>.jsonl (n 묶음으로 나눔)
  LLM 에게 숨길 복지로 분류: 생애주기, 대상특성, 관심주제, 제공유형, 지원주기 → out/llm/bokjiro_tags.csv
복지로 분류는 정확도를 잴 때만 쓴다. LLM 은 글만 보고 분류표(scripts/llm_taxonomy.md)에 맞춰 답한다.

사용:  python3 -I scripts/lcgv_prepare.py [--sido 경상북도] [--parts 3]
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RAW, write_csv

TEXT = ("servNm", "servDgst", "sprtTrgtCn", "slctCritCn", "alwServCn")
TAGS = ("lifeNmArray", "trgterIndvdlNmArray", "intrsThemaNmArray", "srvPvsnNm", "sprtCycNm")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sido", default="경상북도")
    p.add_argument("--parts", type=int, default=3)
    a = p.parse_args()
    rows, tags = [], []
    for f in sorted((RAW / "api" / "lcgv_detail").glob("*.xml")):
        r = ET.parse(f).getroot()
        if (r.findtext("ctpvNm") or "").strip() != a.sido:
            continue
        g = lambda k: " ".join((r.findtext(k) or "").split())
        sgg = g("sggNm") or "(도)"
        rows.append({"id": g("servId"), "시군": sgg, **{k: g(k) for k in TEXT}})
        tags.append({"id": g("servId"), "시군": sgg, "servNm": g("servNm"), **{k: g(k) for k in TAGS},
                     "lastModYmd": g("lastModYmd"), "bizChrDeptNm": g("bizChrDeptNm")})
    d = OUT / "llm"
    d.mkdir(parents=True, exist_ok=True)
    size = -(-len(rows) // a.parts)
    for n in range(a.parts):
        part = rows[n * size:(n + 1) * size]
        (d / f"input_{n + 1}.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in part))
        print(f"✔ out/llm/input_{n + 1}.jsonl {len(part)}건")
    write_csv(d / "bokjiro_tags.csv", tags, list(tags[0]))
    print(f"✔ out/llm/bokjiro_tags.csv {len(tags)}건 (LLM 에게 주지 않음)")


if __name__ == "__main__":
    main()
