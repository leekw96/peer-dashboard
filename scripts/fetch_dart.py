"""
DART Open API에서 동종업계 비교 데이터를 받아 data/{연도}.json 으로 저장합니다.
GitHub Actions에서 실행되며, API 키는 환경변수 DART_API_KEY(저장소 Secret)로만 받습니다.
키는 어떤 출력 파일에도 기록하지 않습니다.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://opendart.fss.or.kr/api"
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KST = timezone(timedelta(hours=9))

# 비교 대상 기업 (DART 고유번호)
COMPANIES = [
    {"key": "p", "name": "풀무원식품", "code": "00684732"},
    {"key": "d", "name": "동원F&B", "code": "00340917"},
    {"key": "s", "name": "샘표식품", "code": "01167056"},
]

FIRST_YEAR = 2015  # 단일회사 주요계정 API 제공 시작연도

# 최근 연도는 가장 최신 보고서부터 탐색 (사업보고서 → 3분기 → 반기 → 1분기)
REPORTS = [
    ("11011", "사업보고서"),
    ("11014", "3분기보고서"),
    ("11012", "반기보고서"),
    ("11013", "1분기보고서"),
]


def call(endpoint, key, **params):
    params["crtfc_key"] = key
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "peer-dashboard-updater"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            time.sleep(0.3)  # 호출 간격 (rate limit 보호)
            return {
                "status": data.get("status", ""),
                "message": data.get("message", ""),
                "list": data.get("list", []) or [],
            }
        except Exception as e:  # 네트워크 일시 오류 재시도
            last = e
            time.sleep(2 * (attempt + 1))
    return {"status": "net", "message": f"연결 실패: {type(last).__name__}", "list": []}


def detect_report(year, key):
    """해당 연도에 공시된 가장 최신 보고서를 찾는다 (1번째 회사 기준)."""
    for code, label in REPORTS:
        r = call("fnlttSinglAcnt.json", key, corp_code=COMPANIES[0]["code"],
                 bsns_year=year, reprt_code=code, fs_div="OFS")
        if r["status"] == "000" and r["list"]:
            return code, label
        if r["status"] in ("010", "011", "012", "020", "net"):
            # 키 오류·한도초과·연결실패는 탐색을 계속해도 의미 없음
            raise RuntimeError(f"DART 오류 {r['status']}: {r['message']}")
    return None, None


def fetch_year(year, key, reprt_code, reprt_label):
    out = {
        "year": year,
        "reprt_code": reprt_code,
        "reprt_label": reprt_label,
        "fetched_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "companies": {},
    }
    for co in COMPANIES:
        fin = call("fnlttSinglAcnt.json", key, corp_code=co["code"], bsns_year=year,
                   reprt_code=reprt_code, fs_div="OFS")
        emp = call("empSttus.json", key, corp_code=co["code"], bsns_year=year,
                   reprt_code=reprt_code)
        # 전체 재무제표(판관비·대손상각비 등). 용량을 줄이려 손익계산서(IS/CIS)만 보관
        full = call("fnlttSinglAcntAll.json", key, corp_code=co["code"], bsns_year=year,
                    reprt_code=reprt_code, fs_div="OFS")
        full["list"] = [r for r in full["list"] if r.get("sj_div") in ("IS", "CIS")]
        out["companies"][co["key"]] = {"name": co["name"], "fin": fin, "emp": emp, "full": full}
        print(f"  {year} {reprt_label} {co['name']:<8} 재무 {fin['status']}({len(fin['list'])}) "
              f"임직원 {emp['status']}({len(emp['list'])}) 전체손익 {full['status']}({len(full['list'])})")
    return out


def main():
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        sys.exit("DART_API_KEY 환경변수가 없습니다. 저장소 Settings > Secrets 에 등록하세요.")

    DATA_DIR.mkdir(exist_ok=True)
    this_year = datetime.now(KST).year
    force_all = os.environ.get("REFRESH_ALL") == "1"

    for year in range(FIRST_YEAR, this_year + 1):
        path = DATA_DIR / f"{year}.json"
        recent = year >= this_year - 1
        # 지난 연도는 사업보고서 기준 파일이 이미 있으면 다시 받지 않음 (정정공시 반영은 REFRESH_ALL=1)
        if path.exists() and not recent and not force_all:
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
                # 전체 재무제표(full)까지 받아 둔 사업보고서 파일이면 건너뜀
                if old.get("reprt_code") == "11011" and all("full" in c for c in old["companies"].values()):
                    continue
            except Exception:
                pass

        if recent:
            code, label = detect_report(year, key)
        else:
            code, label = "11011", "사업보고서"
        if not code:
            print(f"  {year}: 공시된 보고서 없음 (건너뜀)")
            continue

        data = fetch_year(year, key, code, label)
        ok = sum(1 for c in data["companies"].values() if c["fin"]["status"] == "000")
        if ok == 0:
            print(f"  {year}: 모든 회사 재무데이터 없음 (저장 안 함)")
            continue
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # 연도 목록 인덱스
    years = []
    for p in sorted(DATA_DIR.glob("[0-9][0-9][0-9][0-9].json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        years.append({"year": d["year"], "reprt_code": d["reprt_code"],
                      "reprt_label": d["reprt_label"], "fetched_at": d["fetched_at"]})
    index = {
        "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "companies": [{"key": c["key"], "name": c["name"], "code": c["code"]} for c in COMPANIES],
        "years": years,
    }
    (DATA_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완료: {len(years)}개 연도")


if __name__ == "__main__":
    main()
