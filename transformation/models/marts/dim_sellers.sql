select
    seller_id,
    seller_name,
    seller_city,
    seller_state
from {{ ref('stg_sellers') }}
