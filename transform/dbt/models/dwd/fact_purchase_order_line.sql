-- 采购订单行事实（粒度：po_id + line_no）
-- 在途口径：仅状态=未完成 的行计在途，in_transit = 订购 - 已到货（到货按 po_id+material_id 归集）
with arrived as (
    select po_id, material_id, sum(arrived_qty) as arrived_qty
    from {{ source('ods', 'purchase_arrival') }}
    group by po_id, material_id
)

select
    concat(p.po_id, '-', cast(p.line_no as varchar)) as po_line_key,
    p.po_id,
    p.line_no,
    p.supplier_id,
    p.material_id,
    p.qty,
    p.unit_price,
    p.qty * p.unit_price                             as amount,
    p.order_date,
    p.expected_date,
    p.status,
    coalesce(a.arrived_qty, 0)                       as arrived_qty,
    case when p.status = '未完成'
         then greatest(p.qty - coalesce(a.arrived_qty, 0), 0)
         else 0 end                                  as in_transit_qty
from {{ source('ods', 'purchase_order') }} p
left join arrived a
    on p.po_id = a.po_id and p.material_id = a.material_id
