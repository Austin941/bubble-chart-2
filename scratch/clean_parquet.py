import pandas as pd
df = pd.read_parquet('data/brokers_history.parquet')

def rename_broker(b):
    if b == '信用-??': return '信用-融資'
    if b == '信用-?券': return '信用-融券'
    return b

df['broker_name'] = df['broker_name'].apply(rename_broker)
df.to_parquet('data/brokers_history.parquet', index=False)
print("Renamed and saved.")
