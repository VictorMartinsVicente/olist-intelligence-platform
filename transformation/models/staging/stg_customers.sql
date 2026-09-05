-- Limpa e padroniza a tabela raw de clientes
with source as (
    select * from {{ source('raw', 'olist_customers_dataset') }}
)

select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix::int as customer_zip_code_prefix,
    lower(trim(customer_city)) as customer_city,
    upper(trim(customer_state)) as customer_state
from source
