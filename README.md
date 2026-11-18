# 서울 일별 기온 시계열 분석 (2000–2025)

서울의 일별 기온 26년치(9,497일)로 **추세·계절성·노이즈**를 분리하고, "서울은 얼마나, 그리고 언제 더워지고 있나"에 답하는 분석 프로젝트입니다.

👉 **분석 리포트: [REPORT.md](REPORT.md)** · 대시보드: [docs/DASHBOARD.md](docs/DASHBOARD.md)

## 핵심 결과
- 연평균기온 **+0.30℃/10년** 상승, 2024·2025년이 26년 중 가장 따뜻한 해
- 상승은 **여름(+0.92℃)·봄(+0.60℃)** 에 집중, 겨울은 정체(-0.38℃) — 2000–09 vs 2016–25 비교
- 폭염일(최고 ≥ 33℃) **연 1.2일 → 7.4일**, 열대야 근사(최저 ≥ 25℃) **연 0.4일 → 7.4일**
- 겨울의 기온 변동성은 여름의 2배 이상

## 폴더 구조
```
.
├── REPORT.md                  # 분석 리포트 (주제·질문·데이터·시각화·인사이트·결론·한계·AI 사용 로그)
├── requirements.txt
├── src/
│   ├── fetch_data.py          # 데이터 수집 (Open-Meteo API)
│   └── analysis.py            # 정제 → 시계열 분석 → 그림/결과 저장
├── data/seoul_daily_2000_2025.csv
├── figures/                   # 그림 8개 (fig1 ~ fig8)
├── outputs/                   # summary.json(모든 수치), 연·월 집계, 이상치 목록, 2025 예측값
├── dashboard/                 # 보너스: 정적 웹 대시보드 (index.html + data.js)
└── docs/                      # 대시보드 실행 방법·시나리오·스크린샷
```

## 실행 방법
Python 3.10 이상.

```bash
pip install -r requirements.txt
python src/fetch_data.py      # 1) 데이터 수집 → data/seoul_daily_2000_2025.csv (이미 포함됨, 생략 가능)
python src/analysis.py        # 2) 분석 → figures/, outputs/, dashboard/data.js
python -m http.server 8765 --directory dashboard   # 3) (선택) 대시보드 → http://localhost:8765
```
> Windows에서 한글 출력이 깨지면 `set PYTHONIOENCODING=utf-8` (PowerShell: `$env:PYTHONIOENCODING="utf-8"`) 후 실행하세요.
> 그래프 한글 폰트는 Malgun Gothic(Windows) → AppleGothic(macOS) → NanumGothic(Linux) 순으로 자동 선택됩니다.

## 데이터 출처 · 라이선스
- **출처**: [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) — ECMWF ERA5 / ERA5-Land 재분석 자료 기반
- **조건**: 위도 37.5665, 경도 126.9780 (서울시청), 2000-01-01 ~ 2025-12-31, 일 단위, 시간대 Asia/Seoul
- **변수**: 일평균·최고·최저 기온(2m), 일강수량
- **라이선스**: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — 재사용 시 *"Weather data by Open-Meteo.com"* 표기 필요. 원 재분석 자료는 Copernicus Climate Change Service(C3S) ERA5 기반입니다.
- **주의**: 관측소 값이 아닌 격자 재분석 값이므로 기상청 공식 통계(서울 108 관측소)와 절대값이 다릅니다. 자세한 내용은 REPORT.md 8장 참고.
