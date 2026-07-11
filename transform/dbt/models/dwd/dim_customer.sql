-- 客户维。contact/phone(PII)、credit_limit(FIN) 带 Marking——治理在查询层强制
select
    customer_id,
    name as customer_name,
    contact,
    phone,
    credit_limit
from {{ source('ods', 'customer') }}
