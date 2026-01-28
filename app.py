import os
import sys
import traceback
import threading
import time
import random
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
import uvicorn
import warnings
# import nest_asyncio

# # Allow nested event loops
# nest_asyncio.apply()

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning)

# Load environment variables
load_dotenv()

# --- Imports ---
# import mesa <-- REMOVED
# Custom Lightweight Mesa Implementation to save space (no scipy required)
class Agent:
    def __init__(self, unique_id, model):
        self.unique_id = unique_id
        self.model = model

    def step(self):
        pass

class Model:
    def __init__(self):
        self.schedule = []
        self.running = True

    def step(self):
        pass

# import osmnx as ox  <-- REMOVED
import networkx as nx
import pandas as pd
import numpy as np
# import geopandas as gpd <-- REMOVED
import folium
# from shapely.geometry import Point <-- REMOVED (mostly)

# --- Configuration ---
PORT = int(os.getenv("PORT", 8001))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",")

# --- Pydantic Models ---
class SimulationRequest(BaseModel):
    agents: int = Field(100, ge=10, le=1000)
    flood: bool = False
    steps: int = Field(20, ge=1, le=100)

class OptimizationResponse(BaseModel):
    proposed_locations: List[Dict[str, float]]
    existing_toilets: List[Dict[str, float]] = []
    status: str
    map_generated: bool

class SimulationResponse(BaseModel):
    final_od_count: int
    history: List[int]
    flood_scenario: bool
    total_agents: int

class AggregateSimulationRequest(BaseModel):
    num_agents: int = Field(300, ge=100, le=1000)
    subsidy_active: bool = False
    flood_active: bool = False

class AggregateSimulationResponse(BaseModel):
    history: List[int]
    total_od_events: int
    coverage: float
    revenue: int
    status: str

# --- 1. Data Layer ---
class DigitalTwinBuilder:
    def __init__(self):
        # Kibera bounding box
        self.bbox_tuple = (36.7830, -1.3220, 36.7970, -1.3080)
        self.G = None
        self.toilets = pd.DataFrame() # Initialize as empty DataFrame
        self.rivers = [] # Initialize as empty list
        
    def fetch_data(self, force_refresh: bool = False):
        """Fetch data from static files"""
        if not force_refresh and hasattr(self, '_data_loaded') and self._data_loaded:
            return self.G, self.toilets, self.rivers
            
        print(f"🌍 Loading pre-computed data...")
        
        # Load Graph
        graph_path = "data/kibera_walk.graphml"
        try:
            if os.path.exists(graph_path):
                self.G = nx.read_graphml(graph_path)
                # Convert string attributes to float if needed (GraphML often stores as string)
                # Ensure node x/y are floats
                # Note: osmnx saves with types usually, but let's be safe
                if len(self.G) > 0:
                    sample_node = list(self.G.nodes(data=True))[0]
                    if isinstance(sample_node[1].get('x'), str):
                        for n, d in self.G.nodes(data=True):
                            if 'x' in d: d['x'] = float(d['x'])
                            if 'y' in d: d['y'] = float(d['y'])
                    # Edge weights
                    sample_edge = list(self.G.edges(data=True))[0]
                    if isinstance(sample_edge[2].get('length'), str):
                         for u, v, d in self.G.edges(data=True):
                             if 'length' in d: d['length'] = float(d['length'])

                print(f"✅ Graph loaded with {len(self.G.nodes)} nodes and {len(self.G.edges)} edges")
            else:
                print(f"❌ Graph file not found at {graph_path}")
                self.G = nx.Graph()
        except Exception as e:
            print(f"❌ Error loading graph: {e}")
            self.G = nx.Graph()

        # Load Toilets
        toilets_path = "data/toilets.csv"
        try:
            if os.path.exists(toilets_path):
                self.toilets = pd.read_csv(toilets_path)
                print(f"✅ Total unique toilets found: {len(self.toilets)}")
            else:
                print("⚠️ No toilets file found")
                self.toilets = pd.DataFrame()
        except Exception as e:
            print(f"⚠️ Could not load toilets: {e}")
            self.toilets = pd.DataFrame()

        # Load Rivers
        rivers_path = "data/rivers.json"
        try:
            if os.path.exists(rivers_path):
                with open(rivers_path, 'r') as f:
                    self.rivers = json.load(f)
                print(f"✅ Rivers/streams loaded: {len(self.rivers)}")
            else:
                print("⚠️ No rivers file found")
                self.rivers = []
        except Exception as e:
            print(f"⚠️ Could not load rivers: {e}")
            self.rivers = []
            
        self._data_loaded = True
        return self.G, self.toilets, self.rivers

# Initialize data
builder = DigitalTwinBuilder()
G_WALK, B_TOILETS, B_RIVERS = builder.fetch_data()

# --- Helper: Nearest Node ---
# We no longer have ox.nearest_nodes. Implement a simple one using NumPy.
def get_nearest_nodes(graph, x_vals, y_vals):
    """
    Find nearest nodes in graph for given x, y coordinates.
    Uses generic numpy broadcasting for small-medium graphs.
    """
    if not graph or len(graph.nodes) == 0:
        return []
        
    # Extract graph nodes
    # nodes are usually ints (osmid)
    node_ids = np.array(list(graph.nodes()))
    
    # Extract coordinates
    # We assume 'x' and 'y' attributes exist
    node_coords = np.array([[graph.nodes[n]['x'], graph.nodes[n]['y']] for n in node_ids])
    
    # Target points
    target_coords = np.column_stack((x_vals, y_vals))
    
    # Calculate squared Euclidean distance (no need for sqrt causing performance hit for argmin)
    # Using broadcasting: (M, 1, 2) - (N, 2) -> (M, N, 2)
    # This might be memory heavy for 1000 agents X 3000 nodes = 3M float pairs.
    # For one-by-one or small batches it's fine. 
    # For initial toilet locations (small N), it's fine.
    
    nearest_ids = []
    
    # Do it iteratively if targets length is small to save memory, or vectorized if small graph
    # 3000 nodes is small.
    for target in target_coords:
        dists = np.sum((node_coords - target)**2, axis=1)
        min_idx = np.argmin(dists)
        nearest_ids.append(node_ids[min_idx])
        
    return nearest_ids

# --- 2. Optimization Engine ---
class SanitationOptimizer:
    @staticmethod
    def find_sanitation_deserts(graph, toilets_df, num_suggestions: int = 3):
        print("🧠 Running Optimization Algorithm...")
        nodes = list(graph.nodes(data=True))
        candidate_nodes = [n[0] for n in nodes] # list of node IDs

        if toilets_df is not None and not toilets_df.empty:
            # toilets_df has 'lat', 'lon'
            toilet_pts_x = toilets_df['lon'].values
            toilet_pts_y = toilets_df['lat'].values
            
            print(f"✅ Found {len(toilets_df)} toilet points for optimization")
            
            existing_facility_nodes = get_nearest_nodes(
                graph, 
                toilet_pts_x, 
                toilet_pts_y
            )
        else:
            print("⚠️ No toilet data available, using fallback")
            existing_facility_nodes = [candidate_nodes[0] if candidate_nodes else 0]

        # Approximate Calculation (Random Sampling for speed)
        sample_size = min(200, len(candidate_nodes))
        # Ensure candidate_nodes not empty
        if not candidate_nodes:
            return []
            
        sample_candidates = np.random.choice(candidate_nodes, sample_size, replace=False)
        best_candidates = []

        for cand in sample_candidates:
            try:
                # Calculate distance to NEAREST existing toilet
                dists = []
                for t in existing_facility_nodes:
                    try:
                        dist = nx.shortest_path_length(graph, cand, t, weight='length')
                        dists.append(dist)
                    except (nx.NetworkXNoPath, nx.NodeNotFound):
                        continue
                
                min_dist = min(dists) if dists else 0
                # We want to MAXIMIZE this minimum distance (find the gap)
                best_candidates.append((cand, min_dist))
            except Exception as e:
                continue

        best_candidates.sort(key=lambda x: x[1], reverse=True)
        
        print(f"✅ Optimization complete. Found {min(num_suggestions, len(best_candidates))} suggestions")
        return best_candidates[:num_suggestions]

    # --- SIMULATION ENGINE (AGGREGATE) ---
    @staticmethod
    def run_aggregate_scenario(num_agents, subsidy_active, flood_active):
        OD_Events = 0
        history = []

        # Cost Logic: 5 KES normally, 0 KES if subsidized
        BASE_COST = 5
        EFFECTIVE_COST = 0 if subsidy_active else BASE_COST

        total_served = 0
        
        # Run 50 Ticks
        for t in range(50):
            # 1. Demand (10% of pop needs toilet)
            demand = np.random.poisson(lam=num_agents * 0.1)

            # 2. Capacity (Flood reduces capacity)
            capacity = 100
            if flood_active:
                capacity = int(capacity * 0.4)

            # 3. Service
            served = min(demand, capacity)
            total_served += served
            unserved = demand - served

            # 4. Balking (Flying Toilet Usage)
            if EFFECTIVE_COST > 0:
                od_now = int(unserved * 0.3)  # High failure rate if expensive
            else:
                od_now = int(unserved * 0.05)  # Low failure rate if free

            OD_Events += od_now
            history.append(OD_Events)

        # Revenue Calculation
        total_revenue = total_served * EFFECTIVE_COST
        
        return history, OD_Events, total_revenue

# --- 3. Simulation Model ---
class Resident(Agent):
    def __init__(self, unique_id, model, home_node, income):
        super().__init__(unique_id, model)
        self.unique_id = unique_id
        self.current_node = home_node
        self.wealth = income
        self.bladder = 0

    def step(self):
        self.bladder += np.random.randint(1, 5)
        if self.bladder > 80:
            self.seek_relief()

    def seek_relief(self):
        dist = self.model.get_nearest_toilet_dist(self.current_node)
        if dist > 300 or self.wealth < 5:
            self.model.od_events += 1
            self.bladder = 0
        else:
            self.wealth -= 5
            self.bladder = 0

class KiberaSimulation(Model):
    def __init__(self, num_agents=200, flood_event=False):
        super().__init__()

        self.G = G_WALK
        self.custom_agents_list = []
        self.od_events = 0
        self.nodes = list(self.G.nodes)
        self.flood_active = flood_event

        if not B_TOILETS.empty:
            # Handle conversion from DataFrame to points
            t_x = B_TOILETS['lon'].values
            t_y = B_TOILETS['lat'].values
            
            self.toilet_nodes = get_nearest_nodes(
                self.G, 
                t_x, 
                t_y
            )
        else:
            self.toilet_nodes = [self.nodes[0]] if self.nodes else []

        if self.nodes:
            for i in range(num_agents):
                start_node = np.random.choice(self.nodes)
                a = Resident(i, self, start_node, 50)
                self.custom_agents_list.append(a)

    def get_nearest_toilet_dist(self, node_id):
        try:
            dists = [
                nx.shortest_path_length(self.G, node_id, t, weight='length') 
                for t in self.toilet_nodes
            ]
            return min(dists) if dists else 9999
        except:
            return 9999

    def step(self):
        random.shuffle(self.custom_agents_list)
        for agent in self.custom_agents_list:
            agent.step()

# --- 4. Visualization Module ---
def generate_map(suggestions=[]):
    """Generate an interactive map with proposed locations"""
    print("🗺️ Generating Interactive Map...")
    
    # Kibera center coordinates
    kibera_center = [-1.3127, 36.7903]
    
    m = folium.Map(
        location=kibera_center, 
        zoom_start=16, 
        tiles=None,
        control_scale=True
    )
    
    # 1. Satellite Layer (Esri World Imagery)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite View',
        max_zoom=19
    ).add_to(m)
    
    # 2. Street Map
    folium.TileLayer(
        'OpenStreetMap',
        name='Street Map',
        max_zoom=19
    ).add_to(m)
    
    # 3. Topographic Map
    folium.TileLayer(
        tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        attr='OpenTopoMap',
        name='Topographic',
        max_zoom=17
    ).add_to(m)
    
    # Set satellite as default
    m.add_child(folium.LayerControl())
    
    # Add Kibera boundary rectangle
    folium.Rectangle(
        bounds=[[-1.3220, 36.7830], [-1.3080, 36.7970]],
        color='#FF0000',
        weight=2,
        fill=False,
        popup='Kibera Study Area',
        name='Study Boundary'
    ).add_to(m)
    
    # Add existing toilets if available
    # B_TOILETS is now a pandas DataFrame with lat/lon cols
    if B_TOILETS is not None and not B_TOILETS.empty:
        print(f"📊 Adding {len(B_TOILETS)} existing toilets to map")
        
        # Create a feature group for better organization
        toilet_group = folium.FeatureGroup(name="Existing Toilets", show=True)
        
        for idx, row in B_TOILETS.iterrows():
            try:
                # Get point location
                lat = row['lat']
                lon = row['lon']
                
                # Create detailed popup
                amenity = row.get('amenity', 'N/A')
                popup_html = f"""
                <div style="font-family: Arial; min-width: 200px">
                    <h4 style="color: green; margin: 0">🚽 Existing Toilet</h4>
                    <hr style="margin: 5px 0">
                    <b>Type:</b> {amenity}<br>
                    <b>Latitude:</b> {lat:.6f}<br>
                    <b>Longitude:</b> {lon:.6f}
                </div>
                """
                
                # Create green toilet marker
                folium.Marker(
                    [lat, lon],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"Toilet: {amenity}",
                    icon=folium.Icon(
                        color="green", 
                        icon="toilet", 
                        prefix="fa",
                        icon_color="white"
                    )
                ).add_to(toilet_group)
                
            except Exception as e:
                print(f"⚠️ Skipping toilet {idx}: {e}")
        
        toilet_group.add_to(m)
    else:
        print("⚠️ No existing toilets found in data")
    
    # Add proposed locations
    if suggestions:
        proposed_group = folium.FeatureGroup(name="Proposed Locations", show=True)
        
        for node_id, dist in suggestions:
            try:
                pt = G_WALK.nodes[node_id]
                
                popup_html = f"""
                <div style="font-family: Arial; min-width: 200px">
                    <h4 style="color: red; margin: 0">⭐ Proposed Toilet Site</h4>
                    <hr style="margin: 5px 0">
                    <b>Distance Score:</b> {dist:.1f} meters<br>
                    <b>Latitude:</b> {pt['y']:.6f}<br>
                    <b>Longitude:</b> {pt['x']:.6f}<br>
                    <b>Node ID:</b> {node_id}
                </div>
                """
                
                # Create red star marker
                folium.Marker(
                    [pt['y'], pt['x']],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"Proposed Site (Score: {dist:.1f}m)",
                    icon=folium.Icon(
                        color="red", 
                        icon="star", 
                        prefix="fa",
                        icon_color="white"
                    )
                ).add_to(proposed_group)
                
            except Exception as e:
                print(f"⚠️ Skipping proposed location {node_id}: {e}")
        
        proposed_group.add_to(m)
    
    # Add legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 160px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px; border-radius: 5px; box-shadow: 0 0 10px rgba(0,0,0,0.2);">
    <b style="font-size: 16px; color: #333;">Map Legend</b><br>
    <hr style="margin: 5px 0; border-color: #ddd;">
    <div style="display: flex; align-items: center; margin: 5px 0;">
        <i class="fa fa-toilet" style="color:green; margin-right: 8px;"></i>
        <span>Existing Toilet</span>
    </div>
    <div style="display: flex; align-items: center; margin: 5px 0;">
        <i class="fa fa-star" style="color:red; margin-right: 8px;"></i>
        <span>Proposed Location</span>
    </div>
    <div style="display: flex; align-items: center; margin: 5px 0;">
        <span style="color:#1E90FF; font-weight:bold; margin-right: 8px;">━━━</span>
        <span>Rivers/Streams</span>
    </div>
    <div style="display: flex; align-items: center; margin: 5px 0;">
        <span style="color:#FF0000; font-weight:bold; margin-right: 8px;">━━━</span>
        <span>Study Boundary</span>
    </div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add title
    title_html = '''
    <div style="position: fixed; 
                top: 10px; left: 50px; width: 400px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:16px; padding: 15px; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.3);">
    <b style="font-size: 18px; color: #2c3e50;">Kibera Sanitation Infrastructure Map</b><br>
    <hr style="margin: 8px 0; border-color: #ddd;">
    <div style="font-size: 14px; color: #555;">
    <b>📍 Location:</b> Kibera, Nairobi, Kenya<br>
    <b>📅 Data Source:</b> OpenStreetMap<br>
    <b>🔄 Last Updated:</b> {date}
    </div>
    </div>
    '''.format(date=time.strftime("%Y-%m-%d %H:%M:%S"))
    
    m.get_root().html.add_child(folium.Element(title_html))

    map_path = "generated_map.html"
    m.save(map_path)
    
    print(f"✅ Map saved as '{map_path}'")
    print(f"   - {len(B_TOILETS) if not B_TOILETS.empty else 0} existing toilets")
    print(f"   - {len(suggestions)} proposed locations")
    print(f"   - Satellite view enabled")
    
    return map_path

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("=" * 50)
    print("🚀 Starting K-SISP Platinum API...")
    print(f"📊 Data Status:")
    print(f"   Graph Nodes: {len(G_WALK.nodes) if G_WALK else 0}")
    print(f"   Existing Toilets: {len(B_TOILETS) if not B_TOILETS.empty else 0}")
    print(f"   Rivers/Streams: {len(B_RIVERS) if B_RIVERS else 0}")
    print(f"🌐 Server running on: http://0.0.0.0:{PORT}")
    print("=" * 50)
    yield
    # Shutdown
    print("🛑 Shutting down...")

# --- 5. FastAPI Application ---
app = FastAPI(
    title="K-SISP Platinum API",
    description="Kibera Sanitation Intelligence Platform - Platinum Edition",
    version="3.0.0",
    lifespan=lifespan
)

# CORS Configuration
# Note: Browsers block "Access-Control-Allow-Origin: *" if "Access-Control-Allow-Credentials: true"
# We'll disable credentials if a wildcard is used.
allow_creds = True
if "*" in CORS_ORIGINS:
    allow_creds = False
    print("⚠️ CORS Wildcard detected. Credentials (cookies) disabled.")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for background tasks
simulation_results = {}
optimization_results = {}

@app.get("/")
async def root():
    return {
        "status": "online",
        "version": "platinum-v3",
        "endpoints": {
            "optimize": "/optimize",
            "simulate": "/simulate",
            "simulate/aggregate": "/simulate/aggregate",
            "map": "/map",
            "status": "/status",
            "debug/toilets": "/debug/toilets"
        }
    }

@app.get("/status")
async def status():
    return {
        "data_loaded": builder._data_loaded if hasattr(builder, '_data_loaded') else False,
        "graph_nodes": len(G_WALK.nodes) if G_WALK else 0,
        "toilets_count": len(B_TOILETS) if not B_TOILETS.empty else 0,
        "rivers_count": len(B_RIVERS) if B_RIVERS else 0,
        "bbox": builder.bbox_tuple
    }

@app.get("/debug/toilets")
async def debug_toilets():
    """Debug endpoint to see toilet data"""
    try:
        if B_TOILETS is not None and not B_TOILETS.empty:
            features = []
            for idx, row in B_TOILETS.head(10).iterrows():  # Show first 10
                # Use simple access
                features.append({
                    'index': idx,
                    'amenity': row.get('amenity', 'unknown'),
                    'lat': row['lat'],
                    'lon': row['lon']
                })
            
            return {
                'count': len(B_TOILETS),
                'sample_features': features,
                'columns': list(B_TOILETS.columns)
            }
        else:
            return {
                'count': 0,
                'message': 'No toilet data available'
            }
    except Exception as e:
        return {'error': str(e)}

@app.get("/optimize", response_model=OptimizationResponse)
def get_optimization_suggestions(num_locations: int = 3):
    """Get optimal toilet locations"""
    try:
        suggestions = SanitationOptimizer.find_sanitation_deserts(
            G_WALK, B_TOILETS, num_suggestions=num_locations
        )
        
        results = []
        for node_id, dist in suggestions:
            pt = G_WALK.nodes[node_id]
            results.append({
                "lat": pt['y'], 
                "lon": pt['x'], 
                "score": float(dist),
                "node_id": str(node_id)
            })
        
        map_path = generate_map(suggestions)
        optimization_results['last'] = results
        
        # Serialize existing toilets
        existing_list = []
        if B_TOILETS is not None and not B_TOILETS.empty:
            for idx, row in B_TOILETS.iterrows():
                try:
                    existing_list.append({
                        "lat": row['lat'],
                        "lon": row['lon'],
                        "amenity": row.get('amenity', 'unknown'),
                        "node_id": str(idx)
                    })
                except Exception:
                    continue

        return OptimizationResponse(
            proposed_locations=results,
            existing_toilets=existing_list,
            status="success",
            map_generated=True
        )
    except Exception as e:
        print(f"❌ Optimization error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/simulate/aggregate", response_model=AggregateSimulationResponse)
def run_aggregate_simulation(request: AggregateSimulationRequest):
    """Run aggregate sanitation simulation"""
    try:
        # DEBUG print with clearer formatting
        print(f"🎮 Starting aggregate simulation:")
        print(f"   Agents: {request.num_agents}")
        print(f"   Subsidy: {request.subsidy_active}")
        print(f"   Flood: {request.flood_active}")
        
        history, total, revenue = SanitationOptimizer.run_aggregate_scenario(
            request.num_agents, 
            request.subsidy_active, 
            request.flood_active
        )
        
        # Calculate derived metrics
        coverage = max(0, min(100, ((1 - (total / (request.num_agents * 5))) * 100)))
        if total > 150:
            status = "CRITICAL"
        elif total > 75:
            status = "MODERATE"
        else:
            status = "STABLE"

        print(f"✅ Simulation complete: {total} OD events, {coverage:.1f}% coverage, Revenue: {revenue}, Status: {status}")
        
        return AggregateSimulationResponse(
            history=history,
            total_od_events=total,
            coverage=coverage,
            revenue=revenue,
            status=status
        )
        
    except Exception as e:
        print(f"❌ Simulation error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/simulate", response_model=SimulationResponse)
def run_simulation(request: SimulationRequest):
    """Run sanitation simulation"""
    try:
        print(f"🎮 Starting simulation: {request.agents} agents, flood={request.flood}")
        sim = KiberaSimulation(num_agents=request.agents, flood_event=request.flood)
        history = []
        
        for step in range(request.steps):
            sim.step()
            history.append(sim.od_events)
            
            # Progress update every 5 steps
            if step % 5 == 0:
                print(f"  Step {step}: {sim.od_events} OD events")
        
        response = SimulationResponse(
            final_od_count=sim.od_events,
            history=history,
            flood_scenario=request.flood,
            total_agents=request.agents
        )
        
        simulation_results['last'] = response.dict()
        return response
        
    except Exception as e:
        print(f"❌ Simulation error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/map")
async def get_generated_map():
    """Serve the generated map"""
    map_path = "generated_map.html"
    if not os.path.exists(map_path):
        raise HTTPException(status_code=404, detail="Map not generated yet. Run /optimize first.")
    return FileResponse(map_path)

@app.post("/refresh-data")
async def refresh_osm_data():
    """Force refresh OSM data"""
    return {
        "status": "deprecated", 
        "message": "Live data refresh is disabled in serverless mode. Please run scripts/generate_data.py locally and deploy."
    }



# --- 7. Main Execution ---
if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=PORT,
        reload=True,
        log_level="info"
    )