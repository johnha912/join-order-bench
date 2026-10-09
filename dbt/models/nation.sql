select * from {{ source('tpch_raw', 'nation') }}
