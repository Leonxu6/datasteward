-- 仓库维：仓库 + 库位数
select
    w.warehouse_id,
    w.name as warehouse_name,
    w.type as warehouse_type,
    count(sl.location_id) as location_count
from {{ source('ods', 'warehouse') }} w
left join {{ source('ods', 'storage_location') }} sl on w.warehouse_id = sl.warehouse_id
group by w.warehouse_id, w.name, w.type
