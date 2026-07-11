-- 可发货核查宽表（ADS）：销售订单行粒度（排除已取消）
-- 可发货口径（与 ontology/actions.py create_delivery 提交条件一致）：物料现库存 ≥ 未发数量
select
    f.so_line_key,
    f.so_id,
    f.line_no,
    f.customer_id,
    f.material_id,
    m.material_name,
    f.qty,
    f.delivered_qty,
    f.open_qty,
    coalesce(s.total_stock, 0)                                   as stock_qty,
    (f.open_qty > 0 and coalesce(s.total_stock, 0) >= f.open_qty) as fulfillable,
    least(f.open_qty, coalesce(s.total_stock, 0))                as max_fulfillable_qty
from {{ ref('fact_sales_order_line') }} f
left join {{ ref('dws_material_stock_daily') }} s on f.material_id = s.material_id
left join {{ ref('dim_material') }} m on f.material_id = m.material_id
where f.status != '已取消'
