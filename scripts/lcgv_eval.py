"""LLM 사업 정리 시범(AI 1단계)을 채점한다.

LLM 분류(out/llm/labels_*.jsonl)를 복지로가 사업마다 붙인 분류(out/llm/bokjiro_tags.csv)와 견준다.
복지로 분류는 빈칸이 많고(대상특성 61%) 관심주제는 대부분 '서민금융' 이라 정답이 아니다. 그래서 정확도가 아니라
'일치율' 로 부르고, 채워진 항목만 견준다. 정확도는 사람이 표본을 검수해서 잰다 (out/llm/check_sample.csv).

결과:  out/llm/labels.csv (합친 분류), out/llm/eval.json (숫자), out/llm/check_sample.csv (검수용 표본 30건),
       out/tables/gb_lcgv_supply.csv (시군별 장애인 대상 지자체 사업 수)
사용:  python3 -I scripts/lcgv_eval.py      (lcgv_prepare.py, LLM 분류 다음에)
"""

import collections
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, read_csv, write_csv

D = OUT / "llm"
KEYS = ["id", "대상특성", "장애_세부", "생애주기", "분야", "제공방식", "소득기준", "소득기준_내용", "나이_최소", "나이_최대",
        "거주요건", "발달장애인_낮활동", "메모"]
ALLOWED = {
    "대상특성": {"저소득", "장애인", "보훈대상자", "한부모·조손", "다문화·탈북민", "다자녀"},
    "생애주기": {"영유아", "아동", "청소년", "청년", "중장년", "노년", "임신·출산"},
    "분야": {"생계·소득", "출산·양육", "돌봄", "건강·의료", "주거", "교육", "일자리", "문화·여가", "이동·교통", "기타"},
    "제공방식": {"현금", "현물", "바우처·지역화폐", "서비스", "감면", "융자", "시설입소", "기타"},
    "장애_세부": {"발달장애", "장애일반", ""},
    "소득기준": {"있음", "없음"},
    "거주요건": {"있음", "없음"},
}
# 복지로 제공유형을 분류표의 제공방식으로
PROVISION = {"현금지급": "현금", "현물지급": "현물", "현물대여": "현물", "전자바우처(바우처)": "바우처·지역화폐",
             "실물바우처": "바우처·지역화폐", "지역화폐": "바우처·지역화폐", "프로그램/서비스(서비스)": "서비스",
             "자원봉사": "서비스", "감면": "감면", "현금대여(융자)": "융자", "시설입소": "시설입소", "기타": "기타"}
LIFE = {"임신 · 출산": "임신·출산"}


def split(v):
    return {x.strip() for x in (v or "").split(",") if x.strip()}


def load():
    labels = []
    for f in sorted(D.glob("labels_*.jsonl")):
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if line.strip():
                labels.append(json.loads(line))
    inputs = {}
    for f in sorted(D.glob("input_*.jsonl")):
        for line in f.read_text().splitlines():
            x = json.loads(line)
            inputs[x["id"]] = x
    tags = {r["id"]: r for r in read_csv(D / "bokjiro_tags.csv")}
    return labels, inputs, tags


def check(labels, inputs):
    problems = []
    ids = [x["id"] for x in labels]
    if sorted(ids) != sorted(inputs):
        problems.append(f"id 가 입력과 다름: 빠짐 {len(set(inputs) - set(ids))}, 남음 {len(set(ids) - set(inputs))}, 중복 {len(ids) - len(set(ids))}")
    for x in labels:
        miss = [k for k in KEYS if k not in x]
        if miss:
            problems.append(f"{x.get('id')}: 키 없음 {miss}")
        for k, ok in ALLOWED.items():
            vals = x.get(k, [])
            for v in (vals if isinstance(vals, list) else [vals]):
                if v not in ok:
                    problems.append(f"{x.get('id')}: {k} 에 허용 안 된 값 {v!r}")
    return problems


def pct(a, b):
    return round(100 * a / b, 1) if b else None


def agree_sets(pairs):
    """[(LLM 집합, 복지로 집합)] 의 완전 일치, 겹침, 값별 정밀도와 재현율."""
    exact = sum(1 for l, b in pairs if l == b)
    overlap = sum(1 for l, b in pairs if l & b)
    per = {}
    for v in sorted(set().union(*(l | b for l, b in pairs))) if pairs else []:
        tp = sum(1 for l, b in pairs if v in l and v in b)
        fp = sum(1 for l, b in pairs if v in l and v not in b)
        fn = sum(1 for l, b in pairs if v not in l and v in b)
        per[v] = {"복지로": tp + fn, "LLM": tp + fp, "둘다": tp, "정밀도": pct(tp, tp + fp), "재현율": pct(tp, tp + fn)}
    return {"건수": len(pairs), "완전일치": exact, "완전일치율": pct(exact, len(pairs)),
            "겹침": overlap, "겹침율": pct(overlap, len(pairs)), "값별": per}


def main():
    labels, inputs, tags = load()
    problems = check(labels, inputs)
    for p in problems[:20]:
        print("✋", p)
    if problems:
        sys.exit(f"분류 파일에 문제 {len(problems)}건. 고친 뒤 다시")
    by = {x["id"]: x for x in labels}
    ev = {"사업": len(labels)}

    # 1. 제공방식: 복지로 제공유형이 '기타' 만이 아닌 사업
    pairs = []
    for i, t in tags.items():
        b = {PROVISION[v] for v in split(t["srvPvsnNm"])} - {"기타"}
        if b:
            pairs.append((set(by[i]["제공방식"]) - {"기타"}, b))
    ev["제공방식"] = agree_sets(pairs)

    # 2. 대상특성: 복지로가 채운 사업만
    pairs = [(set(by[i]["대상특성"]), split(t["trgterIndvdlNmArray"])) for i, t in tags.items() if t["trgterIndvdlNmArray"]]
    ev["대상특성"] = agree_sets(pairs)
    empty = [i for i, t in tags.items() if not t["trgterIndvdlNmArray"]]
    found = [i for i in empty if by[i]["대상특성"]]
    ev["대상특성_복지로빈칸"] = {"빈칸": len(empty), "LLM이_찾음": len(found),
                           "찾은_값": collections.Counter(v for i in found for v in by[i]["대상특성"]).most_common()}

    # 3. 생애주기: 복지로가 채운 사업만
    pairs = [(set(by[i]["생애주기"]), {LIFE.get(v, v) for v in split(t["lifeNmArray"])})
             for i, t in tags.items() if t["lifeNmArray"]]
    ev["생애주기"] = agree_sets(pairs)

    # 4. 관심주제 '서민금융' 이 붙은 사업을 LLM 은 어떤 분야로 보았나
    fin = [i for i, t in tags.items() if "서민금융" in split(t["intrsThemaNmArray"])]
    ev["서민금융_태그"] = {"건수": len(fin), "LLM_분야": collections.Counter(by[i]["분야"] for i in fin).most_common()}
    ev["분야"] = collections.Counter(x["분야"] for x in labels).most_common()
    ev["추출"] = {"소득기준_있음": sum(x["소득기준"] == "있음" for x in labels),
                "나이기준_있음": sum(x["나이_최소"] is not None or x["나이_최대"] is not None for x in labels),
                "거주요건_있음": sum(x["거주요건"] == "있음" for x in labels)}

    # 5. 시군별 장애인 대상 사업 (공급 쪽 지표)
    sgg = collections.defaultdict(collections.Counter)
    for i, t in tags.items():
        x = by[i]
        s = sgg[t["시군"]]
        s["지자체사업"] += 1
        s["장애인_대상"] += "장애인" in x["대상특성"]
        s["발달장애_대상"] += x["장애_세부"] == "발달장애"
        s["발달장애인_낮활동"] += bool(x["발달장애인_낮활동"])
    rows = [{"시군": k, **{c: v[c] for c in ("지자체사업", "장애인_대상", "발달장애_대상", "발달장애인_낮활동")}}
            for k, v in sorted(sgg.items(), key=lambda kv: (-kv[1]["장애인_대상"], kv[0]))]
    write_csv(OUT / "tables" / "gb_lcgv_supply.csv", rows, list(rows[0]))
    ev["시군_장애인대상사업"] = {"있는_시군": sum(1 for r in rows if r["장애인_대상"] and r["시군"] != "(도)"),
                         "낮활동_사업": [(i, tags[i]["시군"], tags[i]["servNm"]) for i in by if by[i]["발달장애인_낮활동"]]}

    # 합친 분류와 검수 표본
    flat = []
    for i, t in tags.items():
        x = by[i]
        flat.append({"id": i, "시군": t["시군"], "사업명": t["servNm"],
                     **{k: (", ".join(x[k]) if isinstance(x[k], list) else x[k]) for k in KEYS[1:]},
                     "복지로_대상특성": t["trgterIndvdlNmArray"], "복지로_생애주기": t["lifeNmArray"],
                     "복지로_제공유형": t["srvPvsnNm"], "복지로_관심주제": t["intrsThemaNmArray"]})
    write_csv(D / "labels.csv", flat, list(flat[0]))
    rng = random.Random(20261108)
    sample = rng.sample(sorted(by), 30)
    check_rows = []
    for i in sample:
        x, s = by[i], inputs[i]
        nai = "" if x["나이_최소"] is None and x["나이_최대"] is None else f"{x['나이_최소'] or ''}~{x['나이_최대'] or ''}세"
        check_rows.append({"번호": len(check_rows) + 1, "id": i, "시군": s["시군"], "사업명": s["servNm"],
                           "지원대상(원문)": s["sprtTrgtCn"], "선정기준(원문)": s["slctCritCn"], "지원내용(원문)": s["alwServCn"],
                           "LLM_대상특성": ", ".join(x["대상특성"]) or "없음", "LLM_생애주기": ", ".join(x["생애주기"]) or "제한 없음",
                           "LLM_분야": x["분야"], "LLM_제공방식": ", ".join(x["제공방식"]),
                           "LLM_소득기준": x["소득기준_내용"] or x["소득기준"], "LLM_나이": nai or "없음", "LLM_거주요건": x["거주요건"],
                           "틀린_항목(검수자가 적음)": ""})
    write_csv(D / "check_sample.csv", check_rows, list(check_rows[0]))
    (D / "eval.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1))

    print(f"사업 {ev['사업']}건, 분류 파일 문제 없음")
    for k in ("제공방식", "대상특성", "생애주기"):
        e = ev[k]
        print(f"{k}: 복지로가 채운 {e['건수']}건, 완전 일치 {e['완전일치율']}%, 겹침 {e['겹침율']}%")
        for v, m in e["값별"].items():
            print(f"    {v}: 복지로 {m['복지로']}, LLM {m['LLM']}, 둘 다 {m['둘다']} (정밀도 {m['정밀도']}%, 재현율 {m['재현율']}%)")
    e = ev["대상특성_복지로빈칸"]
    print(f"복지로 대상특성 빈칸 {e['빈칸']}건 가운데 LLM 이 대상을 찾은 것 {e['LLM이_찾음']}건: {e['찾은_값']}")
    print(f"관심주제 '서민금융' {ev['서민금융_태그']['건수']}건의 LLM 분야: {ev['서민금융_태그']['LLM_분야']}")
    print(f"분야: {ev['분야']}")
    print(f"추출: {ev['추출']}")
    print(f"장애인 대상 사업이 있는 시군: {ev['시군_장애인대상사업']['있는_시군']}곳 (도 사업 빼고)")
    print("발달장애인 낮활동 사업:", ev["시군_장애인대상사업"]["낮활동_사업"])
    print("✔ out/llm/labels.csv, eval.json, check_sample.csv, out/tables/gb_lcgv_supply.csv")


if __name__ == "__main__":
    main()
