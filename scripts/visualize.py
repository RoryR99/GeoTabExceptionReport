# scripts/visualize.py

"""
Visualisation module — generates:
  1. An interactive Folium map  (trip_map.html)  — outside-zone trips only
  2. A self-contained HTML dashboard / report (etl_report.html)
"""

from __future__ import annotations
from datetime import datetime
from html import escape
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd

from scripts.logger import logger
from scripts.config import FOLIUM_MAP_PATH, HTML_REPORT_PATH


EXCLUDED_ZONES = {
    "CUS-002543,Honey Comb Fun House",
    "20003888,Jataak Pataak",
    "27171,STEWART SEA BREEZE",
    "20000121, KAPPA CARIBBEAN LTD (NEW)- Glenco",
    "12250,JADE'S CATERING",
    "10003453,BUNNY'S SUPERMARKET"
    "10005465,ROY RAGOONANNAN CAFE",
    "20002901,Shirley Ramoutar",
}

SMJ_LOGO_URL = "https://www.smjaleel.net/wp-content/uploads/2025/04/SMJaleel-Logo-and-tagline-2.png"


def _format_reporting_window(window_start, window_end) -> str:
    """Return a compact reporting-window label."""
    if not window_start or not window_end:
        return "Reporting window unavailable"
    return f"{window_start.strftime('%Y-%m-%d %H:%M UTC')} to {window_end.strftime('%Y-%m-%d %H:%M UTC')}"


def _relative_html_href(target_path: str, source_path: str) -> str:
    """Return a portable href from one generated HTML file to another."""
    target = Path(target_path).resolve()
    source_dir = Path(source_path).resolve().parent
    relative_path = os.path.relpath(target, source_dir)
    return escape(Path(relative_path).as_posix(), quote=True)


# ─────────────────────────────────────────────
# Folium map  (outside-zone trips only)
# ─────────────────────────────────────────────

def generate_folium_map(
    trips_gdf: gpd.GeoDataFrame,
    zones_gdf: gpd.GeoDataFrame,
    window_start=None,
    window_end=None,
    output_path: str = FOLIUM_MAP_PATH,
) -> None:
    """
    Create an interactive Folium map showing only outside-zone trip stops.
    Dark red markers for stops > 10 min, lighter red otherwise.
    Hover tooltip shows key info; click popup shows full details.
    """
    report_window = _format_reporting_window(window_start, window_end)
    report_href = _relative_html_href(HTML_REPORT_PATH, output_path)

    try:
        import folium
        from folium.plugins import MarkerCluster, HeatMap
    except ImportError:
        logger.warning("folium not installed — skipping map generation.")
        return

    if trips_gdf.empty:
        logger.warning("No trips to map.")
        return

    outside_gdf = trips_gdf[
        ~trips_gdf.get("InsideZone", pd.Series(True, index=trips_gdf.index)).fillna(True)
    ]

    if outside_gdf.empty:
        logger.warning("No outside-zone trips to map.")
        return

    lat_med = outside_gdf.geometry.y.median()
    lon_med = outside_gdf.geometry.x.median()

    fmap = folium.Map(location=[lat_med, lon_med], zoom_start=11, tiles="CartoDB positron")
    fmap.get_root().html.add_child(folium.Element(
        f"""
        <div style="
            position: fixed;
            top: 12px;
            left: 50px;
            z-index: 9999;
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid #cdd9ea;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);
            padding: 10px 14px;
            font-family: Arial, sans-serif;
            color: #17324d;
            font-size: 12px;
            line-height: 1.4;
        ">
          <div style="font-weight: 700; color: #1558b0;">Fleet Activity Map</div>
          <div>Reporting window: {report_window}</div>
          <a href="{report_href}" target="_blank" rel="noopener" style="
              display: inline-block;
              margin-top: 6px;
              color: #1558b0;
              font-weight: 700;
              text-decoration: none;
          ">Open ETL report</a>
        </div>
        """
    ))

    # ── Zone layer ──────────────────────────────────────────────────
    zone_layer = folium.FeatureGroup(name="Zones", show=True)
    for _, zone in zones_gdf.iterrows():
        try:
            coords = [(y, x) for x, y in zone.geometry.exterior.coords]
            folium.Polygon(
                locations=coords,
                color="#1a8cff",
                fill=True,
                fill_opacity=0.15,
                weight=2,
                tooltip=zone.get("ZoneName", "Zone"),
                popup=folium.Popup(
                    f"<b>{zone.get('ZoneName', 'Zone')}</b><br>"
                    f"Type: {zone.get('ZoneType', 'N/A')}<br>"
                    f"Comment: {zone.get('Comment', '')}",
                    max_width=300,
                ),
            ).add_to(zone_layer)
        except Exception:
            pass
    zone_layer.add_to(fmap)

    # ── Outside-zone trip markers ────────────────────────────────────
    outside_layer = folium.FeatureGroup(name="Trips — Outside Zone", show=True)
    cluster = MarkerCluster().add_to(outside_layer)

    for _, trip in outside_gdf.iterrows():
        pt = trip.geometry
        if pt is None or pt.is_empty:
            continue

        stop_over = bool(trip.get("StopOver10Min", False))
        icon_name = "time" if stop_over else "exclamation-sign"

        stop_dur = round(float(trip.get("StopDurationMin") or 0), 1)
        dist_km  = trip.get("DistanceKm", "N/A")
        nearest  = trip.get("NearestZone", "N/A")
        device   = trip.get("DeviceName", "N/A")
        plate    = trip.get("LicensePlate", "")
        stop_t   = trip.get("StopTime", "N/A")
        after_h  = "Yes" if trip.get("AfterHoursStop") else "No"
        weekend  = "Yes" if trip.get("WeekendStop") else "No"
        long_s   = "Yes" if trip.get("LongStop") else "No"
        high_i   = "Yes" if trip.get("HighIdle") else "No"
        speed    = trip.get("SpeedKmh", "N/A")
        day      = trip.get("DayOfWeek", "N/A")
        trip_dur = trip.get("TripDurationMin", "N/A")

        popup_html = (
            f"<div style='font-family:Arial;font-size:13px;min-width:270px'>"
            f"<b style='font-size:15px'>🚛 {device}</b><br>"
            f"<span style='color:#777'>Plate: {plate}</span>"
            f"<hr style='margin:6px 0'>"
            f"<b>Nearest Customer:</b> {nearest}<br>"
            f"<b>Distance to Zone:</b> {dist_km} km<br>"
            f"<hr style='margin:6px 0'>"
            f"<b>Stop Time:</b> {stop_t}<br>"
            f"<b>Day:</b> {day}<br>"
            f"<b>Stop Duration:</b> {stop_dur} min<br>"
            f"<b>Trip Duration:</b> {trip_dur} min<br>"
            f"<b>Avg Speed:</b> {speed} km/h<br>"
            f"<hr style='margin:6px 0'>"
            f"<b>Long Stop (&gt;60 min):</b> {long_s}<br>"
            f"<b>After Hours:</b> {after_h}<br>"
            f"<b>Weekend:</b> {weekend}<br>"
            f"<b>High Idle:</b> {high_i}<br>"
            f"</div>"
        )

        tooltip_html = (
            f"<b>{device}</b> → {nearest}<br>"
            f"Stop: {stop_dur} min &nbsp;|&nbsp; Dist: {dist_km} km &nbsp;|&nbsp; {day}"
        )

        folium.Marker(
            location=[pt.y, pt.x],
            icon=folium.Icon(color="darkred" if stop_over else "red", icon=icon_name, prefix="glyphicon"),
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=tooltip_html,
        ).add_to(cluster)

    outside_layer.add_to(fmap)

    # ── Heat map layer ───────────────────────────────────────────────
    heat_data = [
        [row.geometry.y, row.geometry.x]
        for _, row in outside_gdf.iterrows()
        if row.geometry and not row.geometry.is_empty
    ]
    if heat_data:
        heat_layer = folium.FeatureGroup(name="Stop Density Heatmap", show=False)
        HeatMap(heat_data, radius=15, blur=10).add_to(heat_layer)
        heat_layer.add_to(fmap)

    folium.LayerControl(collapsed=False).add_to(fmap)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fmap.save(output_path)
    logger.info(f"Folium map saved: {output_path}")


# ─────────────────────────────────────────────
# HTML dashboard report
# ─────────────────────────────────────────────

def generate_html_report(
    trips_gdf: gpd.GeoDataFrame,
    device_summary: pd.DataFrame,
    zone_summary: pd.DataFrame,
    window_start=None,
    window_end=None,
    output_path: str = HTML_REPORT_PATH,
) -> None:
    """
    Generate a self-contained HTML report with SM Jaleel branding (light blue/white),
    an interactive date filter, KPI cards, Chart.js bar chart,
    outside-zone stops table, device summary, and zone summary.
    """
    import json

    df = pd.DataFrame(trips_gdf.drop(columns="geometry", errors="ignore"))
    report_window = _format_reporting_window(window_start, window_end)
    map_href = _relative_html_href(FOLIUM_MAP_PATH, output_path)

    # ── Apply exclusions ─────────────────────────────────────────────
    if "NearestZone" in df.columns:
        df = df[~df["NearestZone"].isin(EXCLUDED_ZONES)].copy()
    if not zone_summary.empty and "ZoneName" in zone_summary.columns:
        zone_summary = zone_summary[~zone_summary["ZoneName"].isin(EXCLUDED_ZONES)].copy()

    # ── Normalise StopTime for date filter ───────────────────────────
    if "StopTime" in df.columns:
        df["StopTime"] = pd.to_datetime(df["StopTime"], errors="coerce", utc=True).dt.tz_localize(None)
        df["_StopDate"] = df["StopTime"].dt.strftime("%Y-%m-%d").fillna("")
    else:
        df["_StopDate"] = ""

    valid_dates = df["_StopDate"][df["_StopDate"] != ""].sort_values()
    date_min = valid_dates.iloc[0]  if not valid_dates.empty else ""
    date_max = valid_dates.iloc[-1] if not valid_dates.empty else ""

    # ── KPI counts ───────────────────────────────────────────────────
    total_trips       = len(df)
    inside_count      = int(df["InsideZone"].sum())       if "InsideZone"     in df.columns else 0
    outside_count     = total_trips - inside_count
    after_hours_count = int(df["AfterHoursStop"].sum())   if "AfterHoursStop" in df.columns else 0
    weekend_count     = int(df["WeekendStop"].sum())      if "WeekendStop"    in df.columns else 0
    long_stop_count   = int(df["LongStop"].sum())         if "LongStop"       in df.columns else 0
    high_idle_count   = int(df["HighIdle"].sum())         if "HighIdle"       in df.columns else 0
    avg_dist          = round(df["DistanceKm"].mean(), 2) if "DistanceKm"     in df.columns else 0
    total_devices     = df["DeviceID"].nunique()           if "DeviceID"       in df.columns else 0

    run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Chart data ───────────────────────────────────────────────────
    if not device_summary.empty and "TotalTrips" in device_summary.columns:
        top_devices  = device_summary.nlargest(15, "TotalTrips")
        chart_labels = list(top_devices["DeviceName"].astype(str))
        chart_values = list(top_devices["TotalTrips"].astype(int))
    else:
        chart_labels, chart_values = [], []

    # ── Outside-zone + stopped >10 min table ─────────────────────────
    OUTSIDE_COLS = [
        "DeviceName", "LicensePlate", "NearestZone", "DistanceKm",
        "StopTime", "DayOfWeek", "StopDurationMin", "LongStop",
        "AfterHoursStop", "WeekendStop", "HighIdle", "SpeedKmh",
    ]
    outside_mask = (
        (~df.get("InsideZone",    pd.Series(True,  index=df.index)).fillna(True)) &
        ( df.get("StopOver10Min", pd.Series(False, index=df.index)).fillna(False))
    )
    outside_df = df[outside_mask].copy()
    available_cols = [c for c in OUTSIDE_COLS if c in outside_df.columns]
    outside_df = outside_df[available_cols]
    if "StopDurationMin" in outside_df.columns:
        outside_df = outside_df.sort_values("StopDurationMin", ascending=False)

    # ── JSON for JS filter ───────────────────────────────────────────
    def _safe_val(v):
        if not isinstance(v, (list, dict)) and pd.isna(v):
            return ""
        if isinstance(v, bool):
            return "Yes" if v else "No"
        if hasattr(v, "isoformat"):
            return str(v)
        return str(v)

    outside_rows_json = json.dumps([
        {col: _safe_val(row[col]) for col in outside_df.columns}
        for _, row in outside_df.iterrows()
    ])
    outside_cols_json = json.dumps(list(outside_df.columns))

    all_rows_json = json.dumps([
        {
            "_StopDate":        str(row.get("_StopDate", "")),
            "InsideZone":       bool(row.get("InsideZone", True)),
            "AfterHoursStop":   bool(row.get("AfterHoursStop", False)),
            "WeekendStop":      bool(row.get("WeekendStop", False)),
            "LongStop":         bool(row.get("LongStop", False)),
            "HighIdle":         bool(row.get("HighIdle", False)),
            "DistanceKm":       float(row["DistanceKm"]) if pd.notna(row.get("DistanceKm")) else 0,
            "DeviceID":         str(row.get("DeviceID", "")),
            "StopOver10Min":    bool(row.get("StopOver10Min", False)),
        }
        for _, row in df.iterrows()
    ])

    # ── Device / zone table HTML helpers ────────────────────────────
    def _tbl(dataframe: pd.DataFrame, max_rows: int = 200) -> str:
        if dataframe.empty:
            return "<tr><td colspan='99' style='color:#999;text-align:center;padding:16px'>No data</td></tr>"
        rows = []
        for _, row in dataframe.head(max_rows).iterrows():
            cells = "".join(f"<td>{v}</td>" for v in row)
            rows.append(f"<tr>{cells}</tr>")
        return "".join(rows)

    def _thead(dataframe: pd.DataFrame) -> str:
        return "<tr>" + "".join(f"<th>{c}</th>" for c in dataframe.columns) + "</tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SM Jaleel — Fleet Activity Report — {run_time}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {{
    --blue:       #1a73e8;
    --blue-dk:    #1558b0;
    --blue-lt:    #e8f0fe;
    --blue-mid:   #4a90d9;
    --white:      #ffffff;
    --bg:         #f4f7fb;
    --border:     #d0dff5;
    --text:       #1c2b3a;
    --muted:      #6b7e99;
    --green:      #1e8c5a;
    --orange:     #e07b00;
    --red:        #d32f2f;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg); color: var(--text); }}

  /* ── Header ── */
  header {{
    background: var(--white);
    border-bottom: 3px solid var(--blue);
    padding: 0 36px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 76px;
    box-shadow: 0 2px 10px rgba(26,115,232,.1);
  }}
  .header-left {{ display: flex; align-items: center; gap: 18px; }}
  .header-logo {{ height: 52px; width: auto; object-fit: contain; }}
  .header-divider {{ width: 1px; height: 36px; background: var(--border); }}
  .header-title {{ font-size: 1.1rem; font-weight: 700; color: var(--blue-dk); line-height: 1.3; }}
  .header-title span {{ display: block; font-size: .78rem; font-weight: 400; color: var(--muted); }}
  .header-right {{ font-size: .78rem; color: var(--muted); text-align: right; line-height: 1.6; }}
  .artifact-link {{
    display: inline-block;
    margin-top: 5px;
    color: var(--blue-dk);
    font-weight: 700;
    text-decoration: none;
  }}
  .artifact-link:hover {{ text-decoration: underline; }}

  /* ── Filter bar ── */
  .filter-bar {{
    background: var(--blue-lt);
    border-bottom: 1px solid var(--border);
    padding: 11px 36px;
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
  }}
  .filter-bar label {{ font-size: .83rem; font-weight: 600; color: var(--blue-dk); }}
  .filter-bar input[type=date] {{
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 5px 10px;
    font-size: .83rem;
    color: var(--text);
    background: var(--white);
    outline: none;
  }}
  .filter-bar input[type=date]:focus {{ border-color: var(--blue); box-shadow: 0 0 0 2px rgba(26,115,232,.2); }}
  .btn-apply {{
    background: var(--blue); color: var(--white);
    border: none; border-radius: 6px;
    padding: 6px 18px; font-size: .83rem; font-weight: 600;
    cursor: pointer; transition: background .15s;
  }}
  .btn-apply:hover {{ background: var(--blue-dk); }}
  .btn-clear {{
    background: var(--white); color: var(--muted);
    border: 1px solid var(--border); border-radius: 6px;
    padding: 6px 14px; font-size: .83rem;
    cursor: pointer; transition: background .15s;
  }}
  .btn-clear:hover {{ background: var(--border); }}
  #filter-status {{ font-size: .8rem; color: var(--blue); font-weight: 600; }}

  /* ── Layout ── */
  .container {{ max-width: 1440px; margin: 26px auto; padding: 0 24px; }}

  /* ── KPI grid ── */
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 14px; margin-bottom: 26px; }}
  .kpi {{
    background: var(--white);
    border-radius: 10px;
    padding: 18px 14px;
    text-align: center;
    box-shadow: 0 1px 6px rgba(26,115,232,.08);
    border-top: 3px solid var(--border);
    transition: box-shadow .15s;
  }}
  .kpi:hover {{ box-shadow: 0 4px 14px rgba(26,115,232,.14); }}
  .kpi.neutral {{ border-top-color: var(--blue-mid); }}
  .kpi.ok      {{ border-top-color: var(--green); }}
  .kpi.warn    {{ border-top-color: var(--orange); }}
  .kpi.danger  {{ border-top-color: var(--red); }}
  .kpi .val    {{ font-size: 1.85rem; font-weight: 800; color: var(--blue-dk); }}
  .kpi.ok    .val {{ color: var(--green); }}
  .kpi.warn  .val {{ color: var(--orange); }}
  .kpi.danger .val {{ color: var(--red); }}
  .kpi .lbl  {{ font-size: .72rem; color: var(--muted); margin-top: 5px; text-transform: uppercase; letter-spacing: .05em; }}

  /* ── Cards ── */
  .card {{
    background: var(--white);
    border-radius: 12px;
    box-shadow: 0 1px 6px rgba(26,115,232,.08);
    margin-bottom: 26px;
    border: 1px solid var(--border);
  }}
  .card-header {{
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
    font-weight: 700;
    font-size: .98rem;
    color: var(--blue-dk);
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--blue-lt);
    border-radius: 12px 12px 0 0;
  }}
  .card-body {{ padding: 18px; overflow-x: auto; }}

  /* ── Tables ── */
  table {{ width: 100%; border-collapse: collapse; font-size: .81rem; }}
  th {{
    background: var(--blue);
    color: var(--white);
    padding: 9px 12px;
    text-align: left;
    white-space: nowrap;
    font-weight: 600;
  }}
  th:first-child {{ border-radius: 6px 0 0 0; }}
  th:last-child  {{ border-radius: 0 6px 0 0; }}
  td {{ padding: 7px 12px; border-bottom: 1px solid var(--blue-lt); white-space: nowrap; }}
  tr:hover td {{ background: var(--blue-lt); }}

  /* ── Badges ── */
  .badge {{
    display: inline-block; padding: 2px 9px;
    border-radius: 12px; font-size: .72rem; font-weight: 700;
  }}
  .badge-blue   {{ background: var(--blue-lt);   color: var(--blue-dk); }}
  .badge-orange {{ background: #fff3e0; color: #b35900; }}

  canvas {{ max-height: 340px; }}

  footer {{
    text-align: center; padding: 22px;
    color: var(--muted); font-size: .77rem;
    border-top: 1px solid var(--border);
    margin-top: 8px;
  }}
  footer img {{ height: 22px; vertical-align: middle; margin-right: 8px; opacity: .7; }}
</style>
</head>
<body>

<!-- ── Header ── -->
<header>
  <div class="header-left">
    <img
      class="header-logo"
      src="{SMJ_LOGO_URL}"
      alt="SM Jaleel & Co. Ltd"
      onerror="this.style.display='none';document.getElementById('fallback-name').style.display='block'">
    <span id="fallback-name" style="display:none;font-weight:900;font-size:1.2rem;color:var(--blue-dk)">SM Jaleel &amp; Co. Ltd</span>
    <div class="header-divider"></div>
    <div class="header-title">
      Fleet Activity Report
      <span>GeoTab ETL &nbsp;·&nbsp; Generated: {run_time}</span>
      <span>Reporting window: {report_window}</span>
    </div>
  </div>
  <div class="header-right">
    <b style="color:var(--blue-dk)">{total_trips}</b> trips &nbsp;·&nbsp; <b style="color:var(--blue-dk)">{total_devices}</b> vehicles<br>
    <span>{len(EXCLUDED_ZONES)} internal zones excluded</span><br>
    <a class="artifact-link" href="{map_href}" target="_blank" rel="noopener">Open interactive map</a>
  </div>
</header>

<!-- ── Date filter ── -->
<div class="filter-bar">
  <label>Filter by Stop Date:</label>
  <input type="date" id="dateFrom" value="{date_min}" min="{date_min}" max="{date_max}">
  <span style="color:var(--muted);font-size:.83rem">to</span>
  <input type="date" id="dateTo"   value="{date_max}" min="{date_min}" max="{date_max}">
  <button class="btn-apply" onclick="applyFilter()">Apply</button>
  <button class="btn-clear"  onclick="clearFilter()">Clear</button>
  <span id="filter-status"></span>
</div>

<div class="container">

  <!-- KPI Cards -->
  <div class="kpi-grid">
    <div class="kpi neutral"><div class="val" id="kpi-total">{total_trips}</div><div class="lbl">Total Trips</div></div>
    <div class="kpi ok"><div class="val" id="kpi-inside">{inside_count}</div><div class="lbl">Inside Zone</div></div>
    <div class="kpi danger"><div class="val" id="kpi-outside">{outside_count}</div><div class="lbl">Outside Zone</div></div>
    <div class="kpi warn"><div class="val" id="kpi-afterhours">{after_hours_count}</div><div class="lbl">After-Hours Stops</div></div>
    <div class="kpi warn"><div class="val" id="kpi-weekend">{weekend_count}</div><div class="lbl">Weekend Stops</div></div>
    <div class="kpi warn"><div class="val" id="kpi-longstop">{long_stop_count}</div><div class="lbl">Long Stops (&gt;60 min)</div></div>
    <div class="kpi danger"><div class="val" id="kpi-idle">{high_idle_count}</div><div class="lbl">High Idle Events</div></div>
    <div class="kpi neutral"><div class="val" id="kpi-avgdist">{avg_dist}</div><div class="lbl">Avg Dist to Zone (km)</div></div>
    <div class="kpi neutral"><div class="val" id="kpi-devices">{total_devices}</div><div class="lbl">Active Vehicles</div></div>
  </div>

  <!-- Bar chart -->
  <div class="card">
    <div class="card-header">📊 Trips per Vehicle (Top 15)</div>
    <div class="card-body"><canvas id="deviceChart"></canvas></div>
  </div>

  <!-- Outside zone >10 min -->
  <div class="card">
    <div class="card-header">
      ⚠️ Outside Zone Stops &gt; 10 Minutes
      <span class="badge badge-orange" id="outsideBadge">{len(outside_df)} trips</span>
    </div>
    <div class="card-body">
      <table id="outsideTable">
        <thead id="outsideThead"></thead>
        <tbody id="outsideTbody"></tbody>
      </table>
    </div>
  </div>

  <!-- Vehicle summary -->
  <div class="card">
    <div class="card-header">🚛 Vehicle Summary</div>
    <div class="card-body">
      <table>
        <thead>{_thead(device_summary)}</thead>
        <tbody>{_tbl(device_summary)}</tbody>
      </table>
    </div>
  </div>

  <!-- Zone summary -->
  <div class="card">
    <div class="card-header">📍 Zone / Customer Summary</div>
    <div class="card-body">
      <table>
        <thead>{_thead(zone_summary)}</thead>
        <tbody>{_tbl(zone_summary)}</tbody>
      </table>
    </div>
  </div>

</div>

<footer>
  <img src="{SMJ_LOGO_URL}" alt="SMJ" onerror="this.style.display='none'">
  S.M. Jaleel &amp; Co. Ltd &mdash; Fleet Activity Report &mdash; {run_time}
</footer>

<script>
const ALL_ROWS          = {all_rows_json};
const OUT_ROWS          = {outside_rows_json};
const OUT_COLS          = {outside_cols_json};
const CHART_LABELS_ORIG = {chart_labels};
const CHART_VALUES_ORIG = {chart_values};

function renderOutsideTable(rows) {{
  const thead = document.getElementById('outsideThead');
  const tbody = document.getElementById('outsideTbody');
  const badge = document.getElementById('outsideBadge');
  if (!thead.innerHTML) {{
    thead.innerHTML = '<tr>' + OUT_COLS.map(c => `<th>${{c}}</th>`).join('') + '</tr>';
  }}
  tbody.innerHTML = rows.length === 0
    ? "<tr><td colspan='99' style='color:#999;text-align:center;padding:16px'>No data for selected range</td></tr>"
    : rows.map(r => '<tr>' + OUT_COLS.map(c => `<td>${{r[c] ?? ''}}</td>`).join('') + '</tr>').join('');
  badge.textContent = rows.length + ' trips';
}}

function updateKPIs(rows) {{
  const total   = rows.length;
  const inside  = rows.filter(r => r.InsideZone).length;
  const afterH  = rows.filter(r => r.AfterHoursStop).length;
  const weekend = rows.filter(r => r.WeekendStop).length;
  const longS   = rows.filter(r => r.LongStop).length;
  const idle    = rows.filter(r => r.HighIdle).length;
  const dists   = rows.map(r => r.DistanceKm).filter(v => v > 0);
  const avgD    = dists.length ? (dists.reduce((a,b)=>a+b,0)/dists.length).toFixed(2) : 0;
  const devs    = new Set(rows.map(r => r.DeviceID)).size;
  document.getElementById('kpi-total').textContent      = total;
  document.getElementById('kpi-inside').textContent     = inside;
  document.getElementById('kpi-outside').textContent    = total - inside;
  document.getElementById('kpi-afterhours').textContent = afterH;
  document.getElementById('kpi-weekend').textContent    = weekend;
  document.getElementById('kpi-longstop').textContent   = longS;
  document.getElementById('kpi-idle').textContent       = idle;
  document.getElementById('kpi-avgdist').textContent    = avgD;
  document.getElementById('kpi-devices').textContent    = devs;
}}

function applyFilter() {{
  const from = document.getElementById('dateFrom').value;
  const to   = document.getElementById('dateTo').value;
  const filtAll = ALL_ROWS.filter(r => (!from || r._StopDate >= from) && (!to || r._StopDate <= to));
  const filtOut = OUT_ROWS.filter(r => {{
    const d = (r.StopTime || '').slice(0, 10);
    return (!from || d >= from) && (!to || d <= to);
  }});
  updateKPIs(filtAll);
  renderOutsideTable(filtOut);
  document.getElementById('filter-status').textContent =
    (from || to) ? `Showing ${{filtAll.length}} of ${{ALL_ROWS.length}} trips` : '';
}}

function clearFilter() {{
  document.getElementById('dateFrom').value = '{date_min}';
  document.getElementById('dateTo').value   = '{date_max}';
  updateKPIs(ALL_ROWS);
  renderOutsideTable(OUT_ROWS);
  document.getElementById('filter-status').textContent = '';
}}

new Chart(document.getElementById('deviceChart'), {{
  type: 'bar',
  data: {{
    labels: CHART_LABELS_ORIG,
    datasets: [{{
      label: 'Total Trips',
      data: CHART_VALUES_ORIG,
      backgroundColor: '#1a73e8',
      hoverBackgroundColor: '#1558b0',
      borderRadius: 5,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ beginAtZero: true, grid: {{ color: '#e8f0fe' }} }},
      x: {{ grid: {{ display: false }} }}
    }}
  }}
}});

renderOutsideTable(OUT_ROWS);
</script>
</body>
</html>"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"HTML report saved: {output_path}")
