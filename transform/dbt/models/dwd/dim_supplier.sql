-- 供应商维。contact/phone 带 PII Marking——治理在查询层强制，建模层保留原值
select
    supplier_id,
    name as supplier_name,
    contact,
    phone,
    address
from {{ source('ods', 'supplier') }}
