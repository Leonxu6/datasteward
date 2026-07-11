-- 发货事实（粒度：发货单）
select
    delivery_id,
    so_id,
    customer_id,
    material_id,
    qty,
    delivery_date,
    status
from {{ source('ods', 'delivery_note') }}
