-- 业务规则：销售额 = qty × unit_price（允许浮点 1 分误差）；金额不得为负
select *
from {{ ref('fact_sales_order_line') }}
where amount < 0 or abs(amount - qty * unit_price) > 0.01
