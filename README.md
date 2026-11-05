# 동종업계 경영지표 대시보드

풀무원식품 · 동원F&B · 샘표식품의 별도(OFS) 재무제표와 임직원 현황을 DART Open API에서 받아 비교하는 대시보드입니다.
GitHub Pages로 배포되어 URL만 있으면 누구나 볼 수 있습니다.

## 구조

| 파일 | 역할 |
|---|---|
| `index.html` | 대시보드 화면. `data/*.json`만 읽으며 API 키가 없습니다. |
| `scripts/fetch_dart.py` | DART API 호출 → `data/연도.json`, `data/index.json` 생성 |
| `.github/workflows/update.yml` | 매일 07:17(KST)에 데이터 수집 → 커밋 → Pages 배포 |
| `data/` | 수집된 공시 원본 데이터 (자동 생성) |

## 최초 설정 (1회)

1. GitHub에 새 저장소를 만들고 이 폴더의 파일을 모두 올립니다. 기본 브랜치는 `main`입니다.
2. **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `DART_API_KEY`
   - Secret: opendart.fss.or.kr에서 발급받은 인증키
3. **Settings → Pages → Build and deployment → Source** 를 **GitHub Actions** 로 선택합니다.
4. **Actions** 탭 → "DART 데이터 갱신 및 배포" → **Run workflow** 를 눌러 첫 실행합니다.
   첫 실행은 2015년부터 모든 연도를 받으므로 몇 분 걸립니다.
5. 완료되면 **Settings → Pages** 에 표시되는 주소(`https://<계정>.github.io/<저장소>/`)를 직원들에게 공유합니다.

## 운영

- 매일 자동 갱신됩니다. 최근 2개 연도는 매번 다시 받고, 지난 연도는 사업보고서 기준 파일이 있으면 건너뜁니다.
- 정정공시를 반영하려면 Run workflow에서 "지난 연도까지 전부 다시 받기"를 체크해 실행합니다.
- 비교 기업을 바꾸려면 `scripts/fetch_dart.py`의 `COMPANIES`와 `index.html`의 `COS`를 함께 수정합니다.
- 사업보고서가 아직 없는 연도는 가장 최근 분기·반기보고서 기준으로 표시되며, 화면에 누적금액(연환산 아님) 안내가 나옵니다.
