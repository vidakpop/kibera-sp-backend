import osmnx as ox
import networkx as nx
import traceback

print(f"OSMnx Version: {ox.__version__}")

try:
    print("Testing graph_from_bbox...")
    # Attempt to call the function to see if it exists
    if hasattr(ox, 'graph_from_bbox'):
        print("  ox.graph_from_bbox exists.")
    else:
        print("  ERROR: ox.graph_from_bbox does NOT exist.")
except Exception:
    traceback.print_exc()

try:
    print("Testing features_from_bbox...")
    if hasattr(ox, 'features_from_bbox'):
        print("  ox.features_from_bbox exists.")
    else:
        print("  ERROR: ox.features_from_bbox does NOT exist.")
except Exception:
    traceback.print_exc()

try:
    print("Testing nearest_nodes...")
    if hasattr(ox, 'nearest_nodes'):
        print("  ox.nearest_nodes exists.")
    else:
        print("  ERROR: ox.nearest_nodes does NOT exist.")
except Exception:
    traceback.print_exc()
