-- 业务规则：库存数量不得为负（对齐 dm/health/checks.py 的 expectation 检查）
select * from {{ ref('fact_inventory') }} where qty < 0
