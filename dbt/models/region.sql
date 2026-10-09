select * from {{ source('tpch_raw', 'region') }}
