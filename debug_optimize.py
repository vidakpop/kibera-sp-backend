from app import builder, SanitationOptimizer
import traceback

print("Loading data...")
G, toilets, rivers = builder.fetch_data()
print(f"Graph nodes: {len(G.nodes)}")
print(f"Toilets: {len(toilets)}")

try:
    print("Running find_sanitation_deserts...")
    suggestions = SanitationOptimizer.find_sanitation_deserts(G, toilets, num_suggestions=3)
    print("Suggestions:", suggestions)
except Exception:
    traceback.print_exc()
