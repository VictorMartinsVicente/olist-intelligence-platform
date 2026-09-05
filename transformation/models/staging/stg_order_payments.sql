-- Limpa e padroniza a tabela raw de pagamentos
with source as (
    select * from {{ source('raw', 'olist_order_payments_dataset') }}
)

select
    order_id,
    lower(trim(payment_type)) as payment_type,
    payment_installments::int as payment_installments,
    payment_value::numeric as payment_value
from source
