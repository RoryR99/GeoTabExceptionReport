"""Quick environment sanity check — run before the main pipeline."""
import importlib, sys

REQUIRED = ["pandas", "geopandas", "shapely", "pyproj", "requests", "mygeotab", "folium", "openpyxl"]

ok = True
for pkg in REQUIRED:
    try:
        importlib.import_module(pkg)
        print(f"  ✓ {pkg}")
    except ImportError:
        print(f"  ✗ {pkg}  ← NOT INSTALLED")
        ok = False

print("\nEnvironment OK" if ok else "\nEnvironment has missing packages — run: pip install -r requirements.txt")
sys.exit(0 if ok else 1)
