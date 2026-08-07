import duckdb
import pandas as pd
from fredapi import Fred

# Connect — creates credit_scorecard.db file in your folder
conn = duckdb.connect('credit_scorecard.db')

print("Loading CFPB data... (this takes 2-3 minutes)")

# Load directly from CSV — DuckDB handles large files efficiently
conn.execute("""
    CREATE TABLE IF NOT EXISTS complaints AS 
    SELECT * FROM read_csv_auto('complaints.csv', 
                                ignore_errors=True)
""")

# Verify load
count = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
print(f"Loaded {count:,} complaints")

# Check column names — important for writing queries later
cols = conn.execute("DESCRIBE complaints").fetchall()
print("\nColumns in dataset:")
for col in cols:
    print(f"  {col[0]}: {col[1]}")


from fredapi import Fred

fred = Fred(api_key='025f5d62eed27feb927572b1f9629514')

print("\nLoading FRED data...")
delinquency = fred.get_series('DRCCLACBS').reset_index()
delinquency.columns = ['date', 'delinquency_rate']
delinquency = delinquency.dropna()

conn = duckdb.connect('credit_scorecard.db')
conn.execute("DROP TABLE IF EXISTS delinquency")
conn.execute("CREATE TABLE delinquency AS SELECT * FROM delinquency")
print(f"Delinquency data: {len(delinquency)} quarters loaded")
print(f"Range: {delinquency['date'].min()} to {delinquency['date'].max()}")
conn.close()