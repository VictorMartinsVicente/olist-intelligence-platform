-- Limpa e padroniza a tabela raw de produtos
with source as (
    select * from {{ source('raw', 'olist_products_dataset') }}
)

select
    product_id,
    lower(trim(product_category_name)) as product_category_name,
    product_weight_g::numeric as product_weight_g,
    product_length_cm::numeric as product_length_cm,
    product_height_cm::numeric as product_height_cm,
    product_width_cm::numeric as product_width_cm
from source
