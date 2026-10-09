select * from {{ source('tpch_raw', 'supplier') }}
