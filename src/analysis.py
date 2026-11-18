"""서울 일별 기온(2000–2025) 시계열 분석.

실행:  python src/analysis.py
입력:  data/seoul_daily_2000_2025.csv  (src/fetch_data.py로 생성)
출력:  figures/*.png, outputs/summary.json, outputs/*.csv, dashboard/data.js
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "seoul_daily_2000_2025.csv"
FIG = ROOT / "figures"
OUT = ROOT / "outputs"
DASH = ROOT / "dashboard"
for d in (FIG, OUT, DASH):
    d.mkdir(exist_ok=True)

# ------------------------------------------------------------------ 스타일
# 한글 폰트: Windows(Malgun Gothic) → macOS(AppleGothic) → Linux(NanumGothic) 순으로 탐색
_available = {f.name for f in font_manager.fontManager.ttflist}
for _font in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    if _font in _available:
        plt.rcParams["font.family"] = _font
        break
plt.rcParams.update({
    "axes.unicode_minus": False,
    "figure.dpi": 110,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
    "figure.facecolor": "#fcfcfb",
    "axes.facecolor": "#fcfcfb",
    "axes.edgecolor": "#c3c2b7",
    "axes.labelcolor": "#52514e",
    "axes.titlecolor": "#0b0b0b",
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": "#e1e0d9",
    "grid.linewidth": 0.6,
    "xtick.color": "#898781",
    "ytick.color": "#898781",
    "legend.frameon": False,
})
BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
GRAY, INK2 = "#c3c2b7", "#52514e"
DIVERGING = LinearSegmentedColormap.from_list(
    "bwo", ["#104281", "#3987e5", "#f0efec", "#ec835a", "#a3330d"])

HEAT_DAY = 33.0      # 폭염일: 일 최고기온 ≥ 33℃ (기상청 폭염주의보 기준)
TROPICAL_NIGHT = 25.0  # 열대야(근사): 일 최저기온 ≥ 25℃
BASE = (2000, 2009)    # 비교 구간 A
RECENT = (2016, 2025)  # 비교 구간 B

summary: dict = {}


def save(fig, name: str) -> None:
    fig.savefig(FIG / name)
    plt.close(fig)
    print(f"  - figures/{name}")


# ================================================================== 1. 로드 & 기본 정보
df = pd.read_csv(DATA, parse_dates=["date"]).set_index("date").sort_index()
print(f"[1] 로드: {len(df):,}행, {df.index.min().date()} ~ {df.index.max().date()}")
full_range = pd.date_range(df.index.min(), df.index.max(), freq="D")
summary["info"] = {
    "rows": int(len(df)),
    "start": str(df.index.min().date()),
    "end": str(df.index.max().date()),
    "columns": list(df.columns),
    "missing_dates": int(len(full_range.difference(df.index))),
    "duplicated_dates": int(df.index.duplicated().sum()),
    "missing_values": {c: int(v) for c, v in df.isna().sum().items()},
    "describe": df.describe().round(2).to_dict(),
}
print(f"    누락 날짜 {summary['info']['missing_dates']}개, 중복 {summary['info']['duplicated_dates']}개, "
      f"결측값 {summary['info']['missing_values']}")

# ================================================================== 2. 결측치 & 이상치 처리
# (a) 날짜 누락 → 전체 달력으로 reindex 후, 기온은 시간 보간(최대 3일), 강수는 보간하지 않음
df = df.reindex(full_range)
df.index.name = "date"
n_missing_before = int(df[["temp_mean", "temp_max", "temp_min"]].isna().any(axis=1).sum())
for c in ("temp_mean", "temp_max", "temp_min"):
    df[c] = df[c].interpolate("time", limit=3)

# (b) 물리적 범위 검사: 서울 관측 역대 극값(-23.1℃ / 39.6℃)에 여유를 둔 [-30, 45]℃ 밖 → 오류로 간주, NaN
phys_bad = ((df[["temp_mean", "temp_max", "temp_min"]] < -30) |
            (df[["temp_mean", "temp_max", "temp_min"]] > 45)).any(axis=1)
# (c) 논리 일관성: min ≤ mean ≤ max 위반 행
order_bad = ~((df["temp_min"] <= df["temp_mean"] + 1e-9) & (df["temp_mean"] <= df["temp_max"] + 1e-9))
df.loc[phys_bad, ["temp_mean", "temp_max", "temp_min"]] = np.nan

# (d) 통계적 이상치: '계절 대비 편차(anomaly)'의 |z| > 3.5 → 실제 기상 사건일 수 있으므로 삭제하지 않고 플래그만
df["doy_key"] = df.index.strftime("%m-%d")
clim = df.groupby("doy_key")["temp_mean"].mean()
# 일별 기후값은 노이즈가 커서 ±15일 원형 이동평균으로 평활
clim_smooth = pd.concat([clim.iloc[-15:], clim, clim.iloc[:15]]).rolling(31, center=True).mean().iloc[15:-15]
df["clim"] = df["doy_key"].map(clim_smooth)
df["anomaly"] = df["temp_mean"] - df["clim"]
anom_std_by_month = df.groupby(df.index.month)["anomaly"].transform("std")
df["z"] = df["anomaly"] / anom_std_by_month
df["outlier_flag"] = df["z"].abs() > 3.5

outliers = df.loc[df["outlier_flag"], ["temp_mean", "clim", "anomaly", "z"]].round(2)
outliers.to_csv(OUT / "outlier_days.csv")
summary["cleaning"] = {
    "rows_with_missing_temp_before": n_missing_before,
    "physical_range_violations": int(phys_bad.sum()),
    "min_mean_max_order_violations": int(order_bad.sum()),
    "statistical_outliers_flagged(|z|>3.5)": int(df["outlier_flag"].sum()),
    "outlier_examples": outliers.reset_index().assign(date=lambda x: x["date"].dt.strftime("%Y-%m-%d"))
                              .to_dict(orient="records"),
}
print(f"[2] 정제: 물리범위 위반 {phys_bad.sum()}, 순서 위반 {order_bad.sum()}, "
      f"통계적 이상치 플래그 {df['outlier_flag'].sum()}개 (유지)")

df["year"] = df.index.year
df["month"] = df.index.month

# ================================================================== 3. 시계열 기법
# 3-1 이동평균
df["ma30"] = df["temp_mean"].rolling(30, center=True, min_periods=20).mean()
df["ma365"] = df["temp_mean"].rolling(365, center=True, min_periods=365).mean()

# 3-2 연 단위 집계 + 선형 추세
annual = df.groupby("year").agg(
    temp_mean=("temp_mean", "mean"),
    temp_max_mean=("temp_max", "mean"),
    temp_min_mean=("temp_min", "mean"),
    heat_days=("temp_max", lambda s: int((s >= HEAT_DAY).sum())),
    tropical_nights=("temp_min", lambda s: int((s >= TROPICAL_NIGHT).sum())),
    frost_days=("temp_min", lambda s: int((s < 0).sum())),
    precip=("precip", "sum"),
)
annual["yoy_change"] = annual["temp_mean"].diff()          # 변화율(전년 대비 차이, ℃)
annual["yoy_pct"] = annual["temp_mean"].pct_change() * 100  # 변화율(%)
slope, intercept = np.polyfit(annual.index, annual["temp_mean"], 1)
resid = annual["temp_mean"] - (slope * annual.index + intercept)
# 기울기의 표준오차 → 대략적 95% 신뢰구간
se = np.sqrt((resid ** 2).sum() / (len(annual) - 2) / ((annual.index.values - annual.index.values.mean()) ** 2).sum())
annual.round(3).to_csv(OUT / "annual_summary.csv")
summary["trend"] = {
    "slope_per_decade": round(slope * 10, 3),
    "slope_95ci_per_decade": [round((slope - 1.96 * se) * 10, 3), round((slope + 1.96 * se) * 10, 3)],
    "warmest_years": annual["temp_mean"].nlargest(5).round(2).to_dict(),
    "coldest_years": annual["temp_mean"].nsmallest(3).round(2).to_dict(),
    "largest_yoy_rise": {int(annual["yoy_change"].idxmax()): round(annual["yoy_change"].max(), 2)},
    "largest_yoy_drop": {int(annual["yoy_change"].idxmin()): round(annual["yoy_change"].min(), 2)},
    "ma365_first": round(float(df["ma365"].dropna().iloc[0]), 2),
    "ma365_last": round(float(df["ma365"].dropna().iloc[-1]), 2),
}
print(f"[3] 연평균 선형추세: {slope*10:+.2f} ℃/10년 (95% CI {summary['trend']['slope_95ci_per_decade']})")

# 3-3 구간별 통계: 2000–2009 vs 2016–2025, 월별
def period(df_, a, b):
    return df_[(df_["year"] >= a) & (df_["year"] <= b)]

pA, pB = period(df, *BASE), period(df, *RECENT)
monthly_cmp = pd.DataFrame({
    "base_mean": pA.groupby("month")["temp_mean"].mean(),
    "recent_mean": pB.groupby("month")["temp_mean"].mean(),
    "base_max": pA.groupby("month")["temp_max"].mean(),
    "recent_max": pB.groupby("month")["temp_max"].mean(),
    "base_min": pA.groupby("month")["temp_min"].mean(),
    "recent_min": pB.groupby("month")["temp_min"].mean(),
})
monthly_cmp["change"] = monthly_cmp["recent_mean"] - monthly_cmp["base_mean"]
monthly_cmp["change_max"] = monthly_cmp["recent_max"] - monthly_cmp["base_max"]
monthly_cmp["change_min"] = monthly_cmp["recent_min"] - monthly_cmp["base_min"]
# 월별 연평균 계열의 선형 추세(℃/10년)
monthly_series = df.groupby(["year", "month"])["temp_mean"].mean().unstack()
monthly_cmp["trend_per_decade"] = [np.polyfit(monthly_series.index, monthly_series[m], 1)[0] * 10
                                   for m in range(1, 13)]
monthly_cmp.round(3).to_csv(OUT / "monthly_period_comparison.csv")

season_of = {12: "겨울", 1: "겨울", 2: "겨울", 3: "봄", 4: "봄", 5: "봄",
             6: "여름", 7: "여름", 8: "여름", 9: "가을", 10: "가을", 11: "가을"}
season_change = monthly_cmp["change"].groupby(monthly_cmp.index.map(season_of)).mean()
summary["period_compare"] = {
    "base": f"{BASE[0]}-{BASE[1]}", "recent": f"{RECENT[0]}-{RECENT[1]}",
    "annual_mean_base": round(pA["temp_mean"].mean(), 2),
    "annual_mean_recent": round(pB["temp_mean"].mean(), 2),
    "monthly_change": monthly_cmp["change"].round(2).to_dict(),
    "monthly_change_max": monthly_cmp["change_max"].round(2).to_dict(),
    "monthly_change_min": monthly_cmp["change_min"].round(2).to_dict(),
    "monthly_trend_per_decade": monthly_cmp["trend_per_decade"].round(2).to_dict(),
    "season_change": season_change.round(2).to_dict(),
    "heat_days_per_year_base": round(annual.loc[BASE[0]:BASE[1], "heat_days"].mean(), 1),
    "heat_days_per_year_recent": round(annual.loc[RECENT[0]:RECENT[1], "heat_days"].mean(), 1),
    "tropical_nights_base": round(annual.loc[BASE[0]:BASE[1], "tropical_nights"].mean(), 1),
    "tropical_nights_recent": round(annual.loc[RECENT[0]:RECENT[1], "tropical_nights"].mean(), 1),
    "frost_days_base": round(annual.loc[BASE[0]:BASE[1], "frost_days"].mean(), 1),
    "frost_days_recent": round(annual.loc[RECENT[0]:RECENT[1], "frost_days"].mean(), 1),
    "heat_days_by_year": annual["heat_days"].to_dict(),
    "tropical_nights_by_year": annual["tropical_nights"].to_dict(),
}

# 3-4 변동성: 계절 대비 편차(anomaly)의 월별 표준편차 + 전일 대비 변화량
df["dod"] = df["temp_mean"].diff()  # day-over-day 변화(℃)
vol = pd.DataFrame({
    "anomaly_std": df.groupby("month")["anomaly"].std(),
    "dod_abs_mean": df.groupby("month")["dod"].apply(lambda s: s.abs().mean()),
    "dtr_mean": (df["temp_max"] - df["temp_min"]).groupby(df["month"]).mean(),  # 일교차
})
vol_period = pd.DataFrame({
    "anomaly_std_base": pA.groupby("month")["anomaly"].std(),
    "anomaly_std_recent": pB.groupby("month")["anomaly"].std(),
})
vol.join(vol_period).round(3).to_csv(OUT / "monthly_volatility.csv")
big_swings = df["dod"].abs().nlargest(5)
summary["volatility"] = {
    "anomaly_std_by_month": vol["anomaly_std"].round(2).to_dict(),
    "dod_abs_mean_by_month": vol["dod_abs_mean"].round(2).to_dict(),
    "dtr_by_month": vol["dtr_mean"].round(2).to_dict(),
    "anomaly_std_base_vs_recent": vol_period.round(2).to_dict(),
    "largest_day_over_day_swings": {d.strftime("%Y-%m-%d"): round(float(df.loc[d, "dod"]), 1)
                                     for d in big_swings.index},
}

# 3-5 시계열 분해 (가법모형: 관측 = 추세 + 계절 + 잔차)
#   추세 = 365일 중심 이동평균, 계절 = (관측 - 추세)의 월-일별 평균(±15일 평활), 잔차 = 나머지
detr = df["temp_mean"] - df["ma365"]
seas_raw = detr.groupby(df["doy_key"]).mean()
seas_smooth = pd.concat([seas_raw.iloc[-15:], seas_raw, seas_raw.iloc[:15]]).rolling(31, center=True).mean().iloc[15:-15]
seas_smooth -= seas_smooth.mean()
df["seasonal"] = df["doy_key"].map(seas_smooth)
df["resid"] = df["temp_mean"] - df["ma365"] - df["seasonal"]
var_total = df["temp_mean"].var()
summary["decomposition"] = {
    "seasonal_amplitude(max-min)": round(float(seas_smooth.max() - seas_smooth.min()), 2),
    "trend_range": round(float(df["ma365"].max() - df["ma365"].min()), 2),
    "resid_std": round(float(df["resid"].std()), 2),
    "variance_share_seasonal": round(float(df["seasonal"].var() / var_total), 3),
    "variance_share_resid": round(float(df["resid"].var() / var_total), 3),
    "variance_share_trend": round(float(df["ma365"].var() / var_total), 4),
}

# 3-6 베이스라인 예측: 2000–2024로 학습 → 2025년 일평균기온 예측
train, test = df[df["year"] <= 2024], df[df["year"] == 2025].copy()
clim_train = train.groupby("doy_key")["temp_mean"].mean()
clim_train_s = pd.concat([clim_train.iloc[-15:], clim_train, clim_train.iloc[:15]]).rolling(31, center=True).mean().iloc[15:-15]
test["f_naive_last_year"] = df["temp_mean"].shift(365).loc[test.index]       # 계절 나이브: 작년 같은 날
test["f_climatology"] = test["doy_key"].map(clim_train_s)                   # 25년 평균 기후값
ann_tr = train.groupby("year")["temp_mean"].mean()
s_tr, i_tr = np.polyfit(ann_tr.index, ann_tr.values, 1)
offset_2025 = (s_tr * 2025 + i_tr) - ann_tr.mean()
test["f_clim_trend"] = test["f_climatology"] + offset_2025                  # 기후값 + 선형추세 보정
test["f_persistence"] = df["temp_mean"].shift(1).loc[test.index]            # 지속성(어제=오늘) – 참고용

def mae(col): return float((test[col] - test["temp_mean"]).abs().mean())
def rmse(col): return float(np.sqrt(((test[col] - test["temp_mean"]) ** 2).mean()))
def bias(col): return float((test[col] - test["temp_mean"]).mean())

forecast_scores = {c: {"MAE": round(mae(c), 2), "RMSE": round(rmse(c), 2), "bias": round(bias(c), 2)}
                   for c in ("f_naive_last_year", "f_climatology", "f_clim_trend", "f_persistence")}
test["actual_ma30"] = test["temp_mean"].rolling(30, center=True, min_periods=10).mean()
monthly_bias = (test.groupby("month")[["temp_mean", "f_climatology", "f_clim_trend"]].mean()
                .assign(err_clim=lambda x: x["f_climatology"] - x["temp_mean"],
                        err_clim_trend=lambda x: x["f_clim_trend"] - x["temp_mean"]))
summary["forecast_2025"] = {
    "scores": forecast_scores,
    "trend_offset_2025": round(float(offset_2025), 2),
    "actual_2025_mean": round(float(test["temp_mean"].mean()), 2),
    "monthly_error": monthly_bias[["err_clim", "err_clim_trend"]].round(2).to_dict(),
}
test[["temp_mean", "f_naive_last_year", "f_climatology", "f_clim_trend", "f_persistence"]].round(2) \
    .to_csv(OUT / "forecast_2025.csv")
print(f"[3] 2025 예측 MAE: " + ", ".join(f"{k}={v['MAE']}" for k, v in forecast_scores.items()))

# ================================================================== 4. 시각화
print("[4] 그림 저장")
MONTHS = [f"{m}월" for m in range(1, 13)]

# Fig 1 — 원자료 + 이동평균 + 연평균 추세
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["temp_mean"], color=GRAY, lw=0.4, label="일평균기온 (원자료)")
ax.plot(df.index, df["ma30"], color=BLUE, lw=1.2, label="30일 이동평균 (계절 흐름)")
ax.plot(df.index, df["ma365"], color=ORANGE, lw=2.2, label="365일 이동평균 (추세)")
x_mid = pd.to_datetime([f"{y}-07-01" for y in annual.index])
ax.plot(x_mid, slope * annual.index + intercept, color=RED, lw=1.5, ls="--",
        label=f"연평균 선형추세 ({slope*10:+.2f}℃/10년)")
ax.set_title("서울 일평균기온 2000–2025: 큰 계절 진동 위로 천천히 올라가는 추세")
ax.set_ylabel("℃")
ax.legend(loc="lower left", ncol=2, fontsize=9)
ax.set_xlim(df.index.min(), df.index.max())
save(fig, "fig1_trend_moving_average.png")

# Fig 1b — 추세만 확대 (365일 MA)
fig, ax = plt.subplots(figsize=(12, 3.8))
ax.plot(df.index, df["ma365"], color=ORANGE, lw=2.2, label="365일 이동평균")
ax.scatter(x_mid, annual["temp_mean"], s=28, color=BLUE, zorder=3, edgecolor="#fcfcfb", lw=1.5,
           label="연평균")
ax.plot(x_mid, slope * annual.index + intercept, color=RED, lw=1.3, ls="--", label="선형추세")
for y in annual["temp_mean"].nlargest(3).index:
    ax.annotate(f"{y}\n{annual.loc[y,'temp_mean']:.2f}℃", (pd.Timestamp(f"{y}-07-01"), annual.loc[y, "temp_mean"]),
                textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8, color=INK2)
ax.set_title("추세 확대: 365일 이동평균과 연평균기온")
ax.set_ylabel("℃")
ax.legend(loc="upper left", ncol=3, fontsize=9)
ax.set_xlim(df.index.min(), df.index.max())
save(fig, "fig2_annual_trend_zoom.png")

# Fig 3 — 연×월 편차 히트맵
heat = df.groupby(["year", "month"])["anomaly"].mean().unstack()
fig, ax = plt.subplots(figsize=(11, 7))
lim = float(np.nanmax(np.abs(heat.values)))
im = ax.imshow(heat.values, aspect="auto", cmap=DIVERGING, norm=TwoSlopeNorm(0, -lim, lim))
ax.set_xticks(range(12), MONTHS)
ax.set_yticks(range(len(heat.index)), heat.index)
ax.grid(False)
for (i, j), v in np.ndenumerate(heat.values):
    if abs(v) >= 2.5:
        ax.text(j, i, f"{v:+.1f}", ha="center", va="center", fontsize=7,
                color="#ffffff" if abs(v) > lim * 0.6 else "#0b0b0b")
cb = fig.colorbar(im, ax=ax, shrink=0.8)
cb.set_label("평년(2000–2025 일별 기후값) 대비 편차, ℃")
ax.set_title("연·월별 기온 편차: 아래(최근)로 갈수록 붉은 칸이 많아진다")
save(fig, "fig3_anomaly_heatmap.png")

# Fig 4 — 월별 구간 비교 (2000–09 vs 2016–25)
fig, ax = plt.subplots(figsize=(11, 4.5))
x = np.arange(12)
ch = monthly_cmp["change"].values
colors = [ORANGE if v >= 0 else BLUE for v in ch]
ax.bar(x, ch, color=colors, width=0.62)
ax.axhline(0, color="#c3c2b7", lw=1)
for xi, v in zip(x, ch):
    ax.text(xi, v + (0.05 if v >= 0 else -0.05), f"{v:+.2f}", ha="center",
            va="bottom" if v >= 0 else "top", fontsize=9, color=INK2)
ax.set_xticks(x, MONTHS)
ax.margins(y=0.15)
ax.grid(axis="x", visible=False)
ax.set_ylabel("℃")
ax.set_title(f"월별 평균기온 변화: {RECENT[0]}–{RECENT[1]} 평균 - {BASE[0]}–{BASE[1]} 평균")
save(fig, "fig4_monthly_period_change.png")

# Fig 5 — 폭염일 · 열대야 (스몰 멀티플)
fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
for ax, col, color, title in (
        (axes[0], "heat_days", ORANGE, f"폭염일 (일 최고기온 ≥ {HEAT_DAY:.0f}℃)"),
        (axes[1], "tropical_nights", BLUE, f"열대야 근사 (일 최저기온 ≥ {TROPICAL_NIGHT:.0f}℃)")):
    ax.bar(annual.index, annual[col], color=color, width=0.7)
    ma5 = annual[col].rolling(5, center=True, min_periods=3).mean()
    ax.plot(annual.index, ma5, color="#0b0b0b", lw=1.5, label="5년 이동평균")
    for y in annual[col].nlargest(2).index:
        ax.text(y, annual.loc[y, col] + 0.5, f"{y}: {annual.loc[y, col]}일", ha="center", fontsize=8, color=INK2)
    ax.set_title(title, fontsize=11)
    ax.set_ylabel("일수")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(axis="x", visible=False)
fig.suptitle("연간 극한 고온 일수", x=0.01, ha="left", fontsize=13, fontweight="bold")
save(fig, "fig5_extreme_heat_days.png")

# Fig 6 — 시계열 분해
fig, axes = plt.subplots(4, 1, figsize=(12, 9), sharex=True)
axes[0].plot(df.index, df["temp_mean"], color=GRAY, lw=0.4)
axes[0].set_title("관측값", fontsize=11)
axes[1].plot(df.index, df["ma365"], color=ORANGE, lw=1.8)
axes[1].set_title(f"추세 (365일 중심 이동평균) — 범위 {summary['decomposition']['trend_range']}℃", fontsize=11)
axes[2].plot(df.index, df["seasonal"], color=BLUE, lw=0.8)
axes[2].set_title(f"계절성 (월-일별 평균 패턴) — 진폭 {summary['decomposition']['seasonal_amplitude(max-min)']}℃",
                  fontsize=11)
axes[3].plot(df.index, df["resid"], color=INK2, lw=0.3)
axes[3].axhline(0, color=GRAY, lw=0.8)
axes[3].set_title(f"잔차 (노이즈) — 표준편차 {summary['decomposition']['resid_std']}℃", fontsize=11)
for ax in axes:
    ax.set_ylabel("℃")
axes[-1].set_xlim(df.index.min(), df.index.max())
fig.suptitle("가법 시계열 분해: 관측 = 추세 + 계절성 + 잔차", x=0.01, ha="left", fontsize=13, fontweight="bold")
fig.tight_layout()
save(fig, "fig6_decomposition.png")

# Fig 7 — 월별 변동성 (잔차 표준편차, 구간 비교)
fig, ax = plt.subplots(figsize=(11, 4.2))
w = 0.38
ax.bar(x - w / 2, vol_period["anomaly_std_base"], width=w - 0.03, color=BLUE, label=f"{BASE[0]}–{BASE[1]}")
ax.bar(x + w / 2, vol_period["anomaly_std_recent"], width=w - 0.03, color=ORANGE, label=f"{RECENT[0]}–{RECENT[1]}")
ax.set_xticks(x, MONTHS)
ax.set_ylabel("℃ (표준편차)")
ax.set_title("월별 변동성: 계절 대비 편차의 표준편차 — 겨울이 여름보다 훨씬 '출렁인다'")
ax.legend(loc="upper center", ncol=2)
ax.grid(axis="x", visible=False)
save(fig, "fig7_monthly_volatility.png")

# Fig 8 — 2025 베이스라인 예측
fig, ax = plt.subplots(figsize=(12, 4.8))
ax.plot(test.index, test["temp_mean"], color=GRAY, lw=0.8, label="2025 실제 (일평균)")
ax.plot(test.index, test["actual_ma30"], color="#0b0b0b", lw=1.6, label="2025 실제 (30일 이동평균)")
ax.plot(test.index, test["f_climatology"], color=BLUE, lw=1.8,
        label=f"기후값 예측 (MAE {forecast_scores['f_climatology']['MAE']}℃)")
ax.plot(test.index, test["f_clim_trend"], color=ORANGE, lw=1.8, ls="--",
        label=f"기후값+추세 예측 (MAE {forecast_scores['f_clim_trend']['MAE']}℃)")
ax.set_title("베이스라인 예측: 2000–2024 패턴으로 2025년 일평균기온 예측")
ax.set_ylabel("℃")
ax.legend(loc="upper left", fontsize=9)
ax.set_xlim(test.index.min(), test.index.max())
save(fig, "fig8_baseline_forecast_2025.png")

# ================================================================== 5. 결과 저장
with open(OUT / "summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("  - outputs/summary.json")

# 대시보드용 데이터 (날짜, 평균/최고/최저, 강수, 편차)
dash = df[["temp_mean", "temp_max", "temp_min", "precip", "anomaly"]].round(2)
records = [[d.strftime("%Y-%m-%d"), *[None if pd.isna(v) else float(v) for v in row]]
           for d, row in zip(dash.index, dash.values)]
with open(DASH / "data.js", "w", encoding="utf-8") as f:
    f.write("// 자동 생성: python src/analysis.py — [date, mean, max, min, precip, anomaly]\n")
    f.write("window.WEATHER = " + json.dumps(records, separators=(",", ":")) + ";\n")
print("  - dashboard/data.js")
print("완료")
