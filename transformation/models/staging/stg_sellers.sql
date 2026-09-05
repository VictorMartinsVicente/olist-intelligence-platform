-- Limpa e padroniza a tabela raw de vendedores
with source as (
    select * from {{ source('raw', 'olist_sellers_dataset') }}
)

select
    seller_id,
    seller_zip_code_prefix::int as seller_zip_code_prefix,
    lower(trim(seller_city)) as seller_city,
    upper(trim(seller_state)) as seller_state
from source
