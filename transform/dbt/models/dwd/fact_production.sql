-- 生产工单事实（粒度：工单）+ 子件净缺口（应领-已领 之和）
with req as (
    select
        mo_id,
        count(*)                                        as n_components,
        sum(greatest(required_qty - issued_qty, 0))     as component_gap_qty
    from {{ source('ods', 'production_material_req') }}
    group by mo_id
)

select
    po.mo_id,
    po.material_id      as product_material_id,
    po.planned_qty,
    po.completed_qty,
    po.start_date,
    po.due_date,
    po.status,
    coalesce(r.n_components, 0)      as n_components,
    coalesce(r.component_gap_qty, 0) as component_gap_qty
from {{ source('ods', 'production_order') }} po
left join req r on po.mo_id = r.mo_id
