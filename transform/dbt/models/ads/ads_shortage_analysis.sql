-- 缺料分析宽表（ADS）。缺料口径（与 eval 真值 SQL 一致，唯一权威）：
--   物料总库存 < 安全库存 （total_stock < safety_stock）
-- shortage_qty = safety_stock - total_stock（必为正，有 dbt test 把关）
select
    material_id,
    material_name,
    material_type,
    category_name,
    safety_stock,
    total_stock,
    gap_qty as shortage_qty
from {{ ref('dws_material_stock_daily') }}
where total_stock < safety_stock
