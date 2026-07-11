-- 采购建议宽表（ADS）：对缺料物料给出净需求与建议供应商
-- 净需求口径：净需求 = 缺口 - 采购在途（未完成单的 订购-已到货）；建议供应商 = 该物料历史采购行数最多者
with in_transit as (
    select material_id, sum(in_transit_qty) as in_transit_qty
    from {{ ref('fact_purchase_order_line') }}
    group by material_id
),

supplier_rank as (
    select
        material_id,
        supplier_id,
        count(*) as po_line_count,
        row_number() over (partition by material_id order by count(*) desc, supplier_id) as rn
    from {{ ref('fact_purchase_order_line') }}
    group by material_id, supplier_id
)

select
    s.material_id,
    s.material_name,
    s.shortage_qty,
    coalesce(it.in_transit_qty, 0)                            as in_transit_qty,
    greatest(s.shortage_qty - coalesce(it.in_transit_qty, 0), 0) as net_requirement,
    sr.supplier_id                                            as suggested_supplier_id,
    sp.supplier_name                                          as suggested_supplier_name,
    sr.po_line_count                                          as supplier_history_lines
from {{ ref('ads_shortage_analysis') }} s
left join in_transit it on s.material_id = it.material_id
left join (select * from supplier_rank where rn = 1) sr on s.material_id = sr.material_id
left join {{ ref('dim_supplier') }} sp on sr.supplier_id = sp.supplier_id
