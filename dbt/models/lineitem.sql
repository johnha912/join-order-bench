select * from {{ source('tpch_raw', 'lineitem') }}
