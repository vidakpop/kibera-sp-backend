import os
import osmnx as ox
import pandas as pd
import geopandas as gpd
import networkx as nx
import json
from shapely.geometry import Point, LineString, Polygon
import warnings

# Suppress warnings
warnings.filterwarnings("ignore")

# Configuration
# Increase timeout to 600s (10 min) and enable logging
ox.settings.requests_timeout = 600
ox.settings.log_console = True

DATA_DIR = "data"
# Correct order for osmnx 2.x bbox seems to be (West, South, East, North) based on debug
BBOX_TUPLE = (36.7830, -1.3220, 36.7970, -1.3080)  # (North, South, East, West) - wait, osmnx bbox is (north, south, east, west)
# app.py uses: self.bbox_tuple = (36.7830, -1.3220, 36.7970, -1.3080)
# But ox.graph_from_bbox args are (north, south, east, west) usually.
# Let's check how app.py calls it: ox.graph_from_bbox(bbox=self.bbox_tuple, ...)
# If passed as a tuple to bbox arg, it depends on version. In ox 2.0.0 (which is in requirements), it expects (north, south, east, west).
# In app.py: self.bbox_tuple = (36.7830, -1.3220, 36.7970, -1.3080) -> north=36.78, south=-1.32? No.
# Nairobi is roughly 1.3S, 36.8E.
# So -1.32 is South, -1.30 is North. 36.78 is West, 36.79 is East.
# app.py tuple: (36.7830, -1.3220, 36.7970, -1.3080). This looks like (X_min, Y_min, X_max, Y_max) or similar.
# Wait, let's look at app.py line 90: ox.graph_from_bbox(bbox=self.bbox_tuple, ...)
# In recent osmnx, bbox parameter is deprecated in favor of separate n,s,e,w or bbox tuple (north, south, east, west).
# Note: 36.7 is Longitude (East/West). -1.3 is Latitude (North/South).
# So 36... is X, -1... is Y.
# If app.py works, let's just stick to what it passes. However, to be safe, I'll pass the separated values if I can, or just the tuple if that's what app.py did.
# Actually, I'll just use the same tuple and trust it processes correctly or adjust if it fails.
# But wait, coordinate order matters.
# 36.7830 (East?), -1.3220 (South?), 36.7970 (East?), -1.3080 (North?)
# It seems app.py might be using (lon_min, lat_min, lon_max, lat_max) or similar?
# Let's verify standard OSMnx bbox input.
# osmnx.graph_from_bbox(north, south, east, west, ...)
# If passed as tuple: usually (north, south, east, west).
# If values are 36... and -1..., then 36 is North?? No, 36 is Longitude.
# So app.py might be relying on a specific version behavior or unnamed args?
# Line 90: `ox.graph_from_bbox(bbox=self.bbox_tuple, ...)`
# If I look at `app.py`, it imports `osmnx as ox`.
# I'll just use the values explicitly to ensure correctness for the script.
# Latitude: -1.3080 (North), -1.3220 (South).
# Longitude: 36.7970 (East), 36.7830 (West).

NORTH = -1.3080
SOUTH = -1.3220
EAST = 36.7970
WEST = 36.7830

def generate_data():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created {DATA_DIR} directory")

    print("🌍 Fetching Graph from OSM...")
    try:
        # Fetch graph
        # BBOX_TUPLE is (West, South, East, North)
        G = ox.graph_from_bbox(bbox=BBOX_TUPLE, network_type='walk', simplify=True)
        print(f"✅ Graph loaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
        
        # Save graph
        graph_path = os.path.join(DATA_DIR, "kibera_walk.graphml")
        ox.save_graphml(G, filepath=graph_path)
        print(f"✅ Saved graph to {graph_path}")
        
    except Exception as e:
        print(f"❌ Error fetching graph: {e}")
        return

    print("🚽 Fetching Toilets...")
    toilet_tags = [
        {'amenity': 'toilets'},
        {'amenity': 'sanitary_dump_station'},
        {'amenity': 'public_toilet'},
        {'toilets': 'yes'},
        {'toilets': 'public'},
        {'amenity': 'water_point'},
        {'amenity': 'shower'}
    ]
    
    all_toilets = []
    for tags in toilet_tags:
        try:
            toilets = ox.features_from_bbox(bbox=BBOX_TUPLE, tags=tags)
            if not toilets.empty:
                print(f"  Found {len(toilets)} with {tags}")
                all_toilets.append(toilets)
        except Exception as e:
            continue
            
    if all_toilets:
        toilets_gdf = pd.concat(all_toilets).drop_duplicates()
        
        # Convert geometries to Lat/Lon for CSV
        # We want centroids for points/polygons
        if toilets_gdf.crs and not toilets_gdf.crs.is_geographic:
             toilets_gdf = toilets_gdf.to_crs(epsg=4326)
             
        # Extract centroids
        # Warning: centroids of geographic CRS can be slightly off but for small areas usually ok.
        # Better project to 3857, centroid, then back to 4326.
        t_proj = toilets_gdf.to_crs(epsg=3857)
        centroids = t_proj.centroid.to_crs(epsg=4326)
        
        toilets_gdf['lat'] = centroids.y
        toilets_gdf['lon'] = centroids.x
        
        # Keep relevant columns
        cols = ['amenity', 'lat', 'lon']
        # Add name if exists
        if 'name' in toilets_gdf.columns:
            cols.append('name')
            
        final_df = toilets_gdf[cols].copy()
        final_df['amenity'] = final_df['amenity'].fillna('unknown')
        
        csv_path = os.path.join(DATA_DIR, "toilets.csv")
        final_df.to_csv(csv_path, index=False)
        print(f"✅ Saved {len(final_df)} toilets to {csv_path}")
    else:
        print("⚠️ No toilets found")

    print("🌊 Fetching Rivers...")
    tags_w = {'waterway': ['river', 'stream', 'drain']}
    try:
        rivers = ox.features_from_bbox(bbox=BBOX_TUPLE, tags=tags_w)
        if not rivers.empty:
            # We just need geometries for the map (optional) or just metadata
            # app.py uses them mainly for... just reporting count it seems? And maybe future logic.
            # Let's save as GeoJSON to be safe, but a simplified one.
            # actually better: simple dict list
            
            rivers_list = []
            # Project to get consistent coords if needed, but 4326 is fine for folium
            if rivers.crs and not rivers.crs.is_geographic:
                rivers = rivers.to_crs(epsg=4326)

            for idx, row in rivers.iterrows():
                geom = row.geometry
                coords = []
                if geom.geom_type == 'LineString':
                    coords = list(geom.coords)
                elif geom.geom_type == 'MultiLineString':
                    for geom_part in geom.geoms:
                         coords.extend(list(geom_part.coords))
                
                # Setup simple dict
                rivers_list.append({
                    "id": str(idx),
                    "type": geom.geom_type,
                    "coords": coords # [(lon, lat), ...]
                })
                
            json_path = os.path.join(DATA_DIR, "rivers.json")
            with open(json_path, 'w') as f:
                json.dump(rivers_list, f)
            print(f"✅ Saved {len(rivers_list)} rivers to {json_path}")
            
    except Exception as e:
        print(f"⚠️ Error fetching rivers: {e}")

if __name__ == "__main__":
    generate_data()
