import osmnx as ox
from shapely.geometry import Polygon
import traceback

# Kibera coords
NORTH = -1.3080
SOUTH = -1.3220
EAST = 36.7970
WEST = 36.7830

print(f"Bbox: N={NORTH}, S={SOUTH}, E={EAST}, W={WEST}")

try:
    # 1. Create Polygon manually
    p = ox.utils_geo.bbox_to_poly(bbox=(NORTH, SOUTH, EAST, WEST))
    print(f"Polygon WKT: {p.wkt}")
    
    # 2. Check projection
    p_proj, crs = ox.projection.project_geometry(p)
    print(f"Projected CRS: {crs}")
    print(f"Projected Bounds: {p_proj.bounds}")

    # 3. Project back?
    p_reproj, _ = ox.projection.project_geometry(p_proj, crs=crs, to_latlong=True)
    print(f"Reprojected WKT: {p_reproj.wkt}")

    # 4. Try graph download with NO simplifiction to see if it skips projection?
    print("Testing graph_from_bbox dry run...")
    # Just print the query string if possible, or try a tiny box
    
except Exception:
    traceback.print_exc()
