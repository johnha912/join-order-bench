select * from {{ source('tpch_raw', 'part') }}
