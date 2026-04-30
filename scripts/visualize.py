# scripts/visualize.py

import pandas as pd
import folium
from folium.plugins import MarkerCluster
import os

OUTPUT_FILE = "output/processed_truck_stops.csv"  # input CSV
MAP_FILE = "output/stops_map.html"
REPORT_FILE = "output/stops_report.csv"


def main():
    if not os.path.exists(OUTPUT_FILE):
        print("Output CSV not found.")
        return

    df = pd.read_csv(OUTPUT_FILE)
    print(f"Total records: {len(df)}")

    # Filter only: Outside zone & stop >10 mins
    df_filtered = df[(df["InsideZone"] == False) & (df["StopOver10Min"] == True)]
    print(f"Filtered records: {len(df_filtered)}")

    if df_filtered.empty:
        print("No records match filter.")
        return

    # -----------------------------
    # User input filters
    # -----------------------------
    unique_trucks = df_filtered["DeviceName"].unique()
    unique_zones = df_filtered["NearestZone"].unique()

    print("Available trucks:", unique_trucks)
    print("Available zones:", unique_zones)

    # Example: filter by specific truck or zone
    truck_filter = input("Enter truck license plate to filter (or leave blank for all): ").strip()
    zone_filter = input("Enter zone name to filter (or leave blank for all): ").strip()

    if truck_filter:
        df_filtered = df_filtered[df_filtered["DeviceName"] == truck_filter]
    if zone_filter:
        df_filtered = df_filtered[df_filtered["NearestZone"] == zone_filter]

    print(f"Records after filtering: {len(df_filtered)}")
    if df_filtered.empty:
        print("No records after applying filters.")
        return

    # -----------------------------
    # Center map
    # -----------------------------
    center_lat = df_filtered["Latitude"].mean()
    center_lon = df_filtered["Longitude"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles="OpenStreetMap")

    # -----------------------------
    # Marker cluster
    # -----------------------------
    stop_cluster = MarkerCluster(name="Stops >10min Outside Zone").add_to(m)

    for _, row in df_filtered.iterrows():
        popup_text = (
            f"Truck: {row['DeviceName']}<br>"
            f"Nearest Zone: {row['NearestZone']}<br>"
            f"Distance: {row['DistanceKm']} km<br>"
            f"Stop Duration: {row.get('DurationStop', 'N/A')} mins<br>"
            f"Start Time: {row.get('StartTime', '')}<br>"
            f"Stop Time: {row.get('StopTime', '')}"
        )
        # Stop marker
        folium.CircleMarker(
            location=[row["Latitude"], row["Longitude"]],
            radius=5,
            color="red",
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup(popup_text, max_width=300)
        ).add_to(stop_cluster)

        # Nearest zone marker
        folium.Marker(
            location=[row["ZoneLatitude"], row["ZoneLongitude"]],
            icon=folium.Icon(color="blue", icon="info-sign"),
            popup=f"Nearest Zone: {row['NearestZone']}"
        ).add_to(m)

        # Line connecting stop → nearest zone
        folium.PolyLine(
            locations=[
                [row["Latitude"], row["Longitude"]],
                [row["ZoneLatitude"], row["ZoneLongitude"]]
            ],
            color="green",
            weight=1,
            opacity=0.6
        ).add_to(m)

    folium.LayerControl().add_to(m)
    m.save(MAP_FILE)
    print(f"Interactive map saved to {MAP_FILE}")

    # -----------------------------
    # Generate report
    # -----------------------------
    report_cols = [
        "DeviceName", "NearestZone", "DistanceKm", "StopOver10Min",
        "InsideZone", "StartTime", "StopTime", "DurationStop",
        "Latitude", "Longitude", "ZoneLatitude", "ZoneLongitude"
    ]
    df_report = df_filtered[report_cols].copy()
    df_report.to_csv(REPORT_FILE, index=False)
    print(f"Report saved to {REPORT_FILE}")


if __name__ == "__main__":
    main()

