-- 即时库存事实（粒度：物料×仓库×库位，与源同粒度直通清洗）
select
    id,
    material_id,
    warehouse_id,
    location_id,
    qty,
    batch_no,
    update_time
from {{ source('ods', 'inventory') }}
