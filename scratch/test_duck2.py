import pyarrow.parquet as pq
table = pq.read_table('data/brokers_history.parquet')
print("Schema:", table.schema)
