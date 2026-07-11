-- 物料库存日汇总（DWS）：物料粒度，快照日=anchor_today（合成数据锚点，勿用 current_date）
-- gap = 安全库存 - 总库存（正数即缺口）
with stock as (
    select material_id, sum(qty) as total_stock
    from {{ ref('fact_inventory') }}
    group by material_id
)

select
    cast('{{ var("anchor_today") }}' as date)        as snapshot_date,
    m.material_id,
    m.material_name,
    m.material_type,
    m.category_name,
    m.safety_stock,
    coalesce(s.total_stock, 0)                       as total_stock,
    m.safety_stock - coalesce(s.total_stock, 0)      as gap_qty
from {{ ref('dim_material') }} m
left join stock s on m.material_id = s.material_id
