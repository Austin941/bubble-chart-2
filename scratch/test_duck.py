import pandas as pd
df = pd.read_parquet('data/brokers_history.parquet')
print("Total rows:", len(df))
print("Broker names starting with 信用- :")
print(df[df['broker_name'].str.startswith('信用-')]['broker_name'].unique())
print("Broker names containing 信用 :")
print(df[df['broker_name'].str.contains('信用')]['broker_name'].unique())
