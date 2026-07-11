-- 销售主题汇总（DWS）：客户 × 月。销售额口径：状态 ≠ 已取消 的订单行 qty×unit_price 之和
-- （与 ontology/metrics.yaml 的 sales_amount 指标同源；amount 列带 FIN Marking，查询层强制）
select
    f.customer_id,
    c.customer_name,
    date_trunc('month', f.order_date)  as order_month,
    count(distinct f.so_id)            as order_count,
    count(*)                           as line_count,
    sum(f.qty)                         as total_qty,
    sum(f.amount)                      as sales_amount
from {{ ref('fact_sales_order_line') }} f
left join {{ ref('dim_customer') }} c on f.customer_id = c.customer_id
where f.status != '已取消'
group by f.customer_id, c.customer_name, date_trunc('month', f.order_date)
