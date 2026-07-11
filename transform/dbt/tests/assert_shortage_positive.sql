-- 业务规则：缺料表里的缺口必须为正（口径自洽性守卫）
select * from {{ ref('ads_shortage_analysis') }} where shortage_qty <= 0
