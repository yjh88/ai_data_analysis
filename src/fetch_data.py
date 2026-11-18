"""서울 일별 기상 데이터 수집 스크립트.

출처: Open-Meteo Historical Weather API (ERA5 / ERA5-Land 재분석 기반)
      https://open-meteo.com/en/docs/historical-weather-api
라이선스: CC BY 4.0 (출처 표기 필수, "Weather data by Open-Meteo.com")

실행:  python src/fetch_data.py
결과:  data/seoul_daily_2000_2025.csv
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "seoul_daily_2000_2025.csv"

PARAMS = {
    "latitude": 37.5665,       # 서울시청
    "longitude": 126.9780,
    "start_date": "2000-01-01",
    "end_date": "2025-12-31",
    "daily": ",".join([
        "temperature_2m_mean",
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
    ]),
    "timezone": "Asia/Seoul",
}
URL = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(PARAMS)


def main() -> None:
    print(f"요청: {URL}")
    with urllib.request.urlopen(URL, timeout=60) as resp:
        payload = json.load(resp)

    df = pd.DataFrame(payload["daily"]).rename(columns={
        "time": "date",
        "temperature_2m_mean": "temp_mean",
        "temperature_2m_max": "temp_max",
        "temperature_2m_min": "temp_min",
        "precipitation_sum": "precip",
    })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"저장: {OUT}  ({len(df):,}행, {df['date'].iloc[0]} ~ {df['date'].iloc[-1]})")
    print(f"격자 좌표: lat={payload['latitude']}, lon={payload['longitude']}, 고도={payload['elevation']}m")


if __name__ == "__main__":
    main()
