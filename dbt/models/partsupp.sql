select * from {{ source('tpch_raw', 'partsupp') }}
