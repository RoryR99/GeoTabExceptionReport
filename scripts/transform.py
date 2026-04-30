# scripts/transform.py

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from scripts.logger import logger
from datetime import datetime

# -----------------------------
# Create Zones GeoDataFrame
# -----------------------------
def create_zones_gdf(df_zones: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Convert zones DataFrame to GeoDataFrame with Polygon geometry.
    """
    polygons = []
    valid_rows = []

    for _, row in df_zones.iterrows():
        points = row.get("Points", [])
        if not points or len(points) < 3:
            continue
        try:
            poly = Polygon(points)
            if not poly.is_valid:
                poly = poly.buffer(0)
            polygons.append(poly)
            valid_rows.append(row)
        except Exception as e:
            logger.warning(f"Skipping zone {row.get('ZoneID')} due to geometry error: {e}")
            continue

    if not valid_rows:
        logger.warning("No valid zones could be converted to polygons.")
        return gpd.GeoDataFrame(columns=df_zones.columns, geometry=[], crs="EPSG:4326")

    gdf = gpd.GeoDataFrame(valid_rows, geometry=polygons, crs="EPSG:4326")
    logger.info(f"Zones GeoDataFrame created: {len(gdf)} zones")
    return gdf


# -----------------------------
# Create Trips GeoDataFrame
# -----------------------------
def create_trips_gdf(df_trips: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Convert trips DataFrame to GeoDataFrame.
    Only trips with valid lat/lon are kept for spatial operations.
    """
    if "Latitude" not in df_trips.columns or "Longitude" not in df_trips.columns:
        logger.warning("Trips DataFrame missing Latitude/Longitude columns")
        return gpd.GeoDataFrame(columns=df_trips.columns, geometry=[], crs="EPSG:4326")

    df_valid = df_trips.dropna(subset=["Latitude", "Longitude"]).copy()
    logger.info(f"Trips with coordinates: {len(df_valid)} / {len(df_trips)}")
    gdf = gpd.GeoDataFrame(
        df_valid,
        geometry=gpd.points_from_xy(df_valid.Longitude, df_valid.Latitude),
        crs="EPSG:4326"
    )
    return gdf


def spatial_join_nearest(trips_gdf: gpd.GeoDataFrame, zones_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Compute nearest zone for each trip, distance in meters and km,
    whether trip is inside the zone, whether stop duration >10 mins,
    and store nearest zone centroid lat/long.
    """

    if trips_gdf.empty:
        logger.warning("No trips with valid coordinates for spatial join.")
        return trips_gdf

    # Project to metric CRS
    trips_m = trips_gdf.to_crs("EPSG:3857")
    zones_m = zones_gdf.to_crs("EPSG:3857")

    nearest_zone = []
    distance_m = []
    inside_zone = []
    stop_over_10min = []
    zone_lat = []
    zone_lon = []

    for idx, trip in trips_m.iterrows():
        trip_point = trip.geometry

        # -----------------------------
        # StopOver10Min (DurationStop)
        # -----------------------------
        duration_stop = trip.get("DurationStop")

        try:
            import datetime
            if isinstance(duration_stop, datetime.time):
                duration_min = (
                    duration_stop.hour * 60
                    + duration_stop.minute
                    + duration_stop.second / 60
                )
            else:
                duration_min = float(duration_stop or 0)
        except Exception:
            duration_min = 0

        stop_over_10min.append(duration_min > 10)

        # -----------------------------
        # Spatial logic
        # -----------------------------
        if trip_point is None or trip_point.is_empty or zones_m.empty:
            nearest_zone.append(None)
            distance_m.append(None)
            inside_zone.append(False)
            zone_lat.append(None)
            zone_lon.append(None)
            continue

        # Distance to all zones
        distances = zones_m.geometry.distance(trip_point)
        min_idx = distances.idxmin()

        nearest_zone.append(zones_m.loc[min_idx, "ZoneName"])

        dist = distances[min_idx]
        distance_m.append(round(dist, 2))

        polygon = zones_m.loc[min_idx, "geometry"]
        buffer_500m = polygon.buffer(500)
        inside_zone.append(buffer_500m.contains(trip_point))

        # -----------------------------
        # Get centroid (convert back to lat/lon)
        # -----------------------------
        centroid_metric = polygon.centroid

        centroid_geo = gpd.GeoSeries(
            [centroid_metric],
            crs="EPSG:3857"
        ).to_crs("EPSG:4326")

        zone_lon.append(centroid_geo.x.iloc[0])
        zone_lat.append(centroid_geo.y.iloc[0])

    # -----------------------------
    # Assign results
    # -----------------------------
    trips_gdf["NearestZone"] = nearest_zone
    trips_gdf["DistanceMeters"] = distance_m
    trips_gdf["DistanceKm"] = [
        round(m / 1000, 2) if m is not None else None for m in distance_m
    ]
    trips_gdf["InsideZone"] = inside_zone
    trips_gdf["StopOver10Min"] = stop_over_10min
    trips_gdf["ZoneLatitude"] = zone_lat
    trips_gdf["ZoneLongitude"] = zone_lon

    logger.info("Spatial join complete with centroid coordinates.")
    return trips_gdf
