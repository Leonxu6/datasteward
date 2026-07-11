-- 物料维（Kimball 维度表）：物料 + 分类中文名 + 计量单位中文名 + 安全库存
select
    m.material_id,
    m.name          as material_name,
    m.spec,
    m.material_type,
    m.category_id,
    c.name          as category_name,
    m.base_unit_id,
    u.name          as unit_name,
    m.safety_stock
from {{ source('ods', 'material') }} m
left join {{ source('ods', 'material_category') }} c on m.category_id = c.category_id
left join {{ source('ods', 'unit') }} u on m.base_unit_id = u.unit_id
