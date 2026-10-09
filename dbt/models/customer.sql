select * from {{ source('tpch_raw', 'customer') }}
