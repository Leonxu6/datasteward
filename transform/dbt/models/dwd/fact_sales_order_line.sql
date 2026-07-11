-- 销售订单行事实（粒度：so_id + line_no）
-- amount = qty × unit_price；open_qty = 订购 - 已发货（发货单无行号，按 so_id+material_id 归集——口径注记）
with delivered as (
    select so_id, material_id, sum(qty) as delivered_qty
    from {{ source('ods', 'delivery_note') }}
    group by so_id, material_id
)

select
    concat(s.so_id, '-', cast(s.line_no as varchar)) as so_line_key,
    s.so_id,
    s.line_no,
    s.customer_id,
    s.material_id,
    s.qty,
    s.unit_price,
    s.qty * s.unit_price                             as amount,
    s.order_date,
    s.delivery_date,
    s.status,
    coalesce(d.delivered_qty, 0)                     as delivered_qty,
    greatest(s.qty - coalesce(d.delivered_qty, 0), 0) as open_qty
from {{ source('ods', 'sales_order') }} s
left join delivered d
    on s.so_id = d.so_id and s.material_id = d.material_id
