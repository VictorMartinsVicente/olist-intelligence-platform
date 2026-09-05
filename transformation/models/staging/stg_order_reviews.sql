-- Limpa e padroniza a tabela raw de reviews
with source as (
    select * from {{ source('raw', 'olist_order_reviews_dataset') }}
)

select
    order_id,
    review_id,
    review_score::int as review_score,
    review_creation_date::timestamp as review_creation_date
from source
