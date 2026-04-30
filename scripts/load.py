import pandas as pd
from scripts.logger import logger

def export_csv(gdf, filename):
    df = pd.DataFrame(gdf.drop(columns="geometry"))

    df.to_csv(filename, index=False)
    logger.info(f"Exported {len(df)} rows to {filename}")
