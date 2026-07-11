SET 'execution.checkpointing.interval' = '5s';
SET 'pipeline.name' = 'dm-cdc-pg-to-starrocks';

CREATE TABLE `src_company_org` (
  `org_id` STRING,
  `name` STRING,
  `parent_id` STRING,
  `org_type` STRING,
  PRIMARY KEY (`org_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'company_org',
  'slot.name' = 'flink_company_org',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_company_org` (
  `org_id` STRING,
  `name` STRING,
  `parent_id` STRING,
  `org_type` STRING,
  PRIMARY KEY (`org_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'company_org',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_department` (
  `dept_id` STRING,
  `name` STRING,
  `org_id` STRING,
  `parent_id` STRING,
  `manager` STRING,
  PRIMARY KEY (`dept_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'department',
  'slot.name' = 'flink_department',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_department` (
  `dept_id` STRING,
  `name` STRING,
  `org_id` STRING,
  `parent_id` STRING,
  `manager` STRING,
  PRIMARY KEY (`dept_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'department',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_employee` (
  `emp_id` STRING,
  `name` STRING,
  `dept_id` STRING,
  `position` STRING,
  `phone` STRING,
  `status` STRING,
  PRIMARY KEY (`emp_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'employee',
  'slot.name' = 'flink_employee',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_employee` (
  `emp_id` STRING,
  `name` STRING,
  `dept_id` STRING,
  `position` STRING,
  `phone` STRING,
  `status` STRING,
  PRIMARY KEY (`emp_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'employee',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_unit` (
  `unit_id` STRING,
  `name` STRING,
  `symbol` STRING,
  PRIMARY KEY (`unit_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'unit',
  'slot.name' = 'flink_unit',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_unit` (
  `unit_id` STRING,
  `name` STRING,
  `symbol` STRING,
  PRIMARY KEY (`unit_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'unit',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_material_category` (
  `category_id` STRING,
  `name` STRING,
  `parent_id` STRING,
  PRIMARY KEY (`category_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'material_category',
  'slot.name' = 'flink_material_category',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_material_category` (
  `category_id` STRING,
  `name` STRING,
  `parent_id` STRING,
  PRIMARY KEY (`category_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'material_category',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_material` (
  `material_id` STRING,
  `name` STRING,
  `spec` STRING,
  `category_id` STRING,
  `base_unit_id` STRING,
  `material_type` STRING,
  `safety_stock` INT,
  PRIMARY KEY (`material_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'material',
  'slot.name' = 'flink_material',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_material` (
  `material_id` STRING,
  `name` STRING,
  `spec` STRING,
  `category_id` STRING,
  `base_unit_id` STRING,
  `material_type` STRING,
  `safety_stock` INT,
  PRIMARY KEY (`material_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'material',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_unit_conversion` (
  `id` STRING,
  `material_id` STRING,
  `from_unit_id` STRING,
  `to_unit_id` STRING,
  `factor` INT,
  PRIMARY KEY (`id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'unit_conversion',
  'slot.name' = 'flink_unit_conversion',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_unit_conversion` (
  `id` STRING,
  `material_id` STRING,
  `from_unit_id` STRING,
  `to_unit_id` STRING,
  `factor` INT,
  PRIMARY KEY (`id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'unit_conversion',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_warehouse` (
  `warehouse_id` STRING,
  `name` STRING,
  `type` STRING,
  PRIMARY KEY (`warehouse_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'warehouse',
  'slot.name' = 'flink_warehouse',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_warehouse` (
  `warehouse_id` STRING,
  `name` STRING,
  `type` STRING,
  PRIMARY KEY (`warehouse_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'warehouse',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_storage_location` (
  `location_id` STRING,
  `warehouse_id` STRING,
  `code` STRING,
  `name` STRING,
  PRIMARY KEY (`location_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'storage_location',
  'slot.name' = 'flink_storage_location',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_storage_location` (
  `location_id` STRING,
  `warehouse_id` STRING,
  `code` STRING,
  `name` STRING,
  PRIMARY KEY (`location_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'storage_location',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_supplier` (
  `supplier_id` STRING,
  `name` STRING,
  `contact` STRING,
  `phone` STRING,
  `address` STRING,
  PRIMARY KEY (`supplier_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'supplier',
  'slot.name' = 'flink_supplier',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_supplier` (
  `supplier_id` STRING,
  `name` STRING,
  `contact` STRING,
  `phone` STRING,
  `address` STRING,
  PRIMARY KEY (`supplier_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'supplier',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_customer` (
  `customer_id` STRING,
  `name` STRING,
  `contact` STRING,
  `phone` STRING,
  `credit_limit` INT,
  PRIMARY KEY (`customer_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'customer',
  'slot.name' = 'flink_customer',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_customer` (
  `customer_id` STRING,
  `name` STRING,
  `contact` STRING,
  `phone` STRING,
  `credit_limit` INT,
  PRIMARY KEY (`customer_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'customer',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_dictionary` (
  `dict_id` STRING,
  `dict_type` STRING,
  `code` STRING,
  `value` STRING,
  `description` STRING,
  PRIMARY KEY (`dict_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'dictionary',
  'slot.name' = 'flink_dictionary',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_dictionary` (
  `dict_id` STRING,
  `dict_type` STRING,
  `code` STRING,
  `value` STRING,
  `description` STRING,
  PRIMARY KEY (`dict_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'dictionary',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_inventory` (
  `id` STRING,
  `material_id` STRING,
  `warehouse_id` STRING,
  `location_id` STRING,
  `qty` INT,
  `batch_no` STRING,
  `update_time` TIMESTAMP(3),
  PRIMARY KEY (`id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'inventory',
  'slot.name' = 'flink_inventory',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_inventory` (
  `id` STRING,
  `material_id` STRING,
  `warehouse_id` STRING,
  `location_id` STRING,
  `qty` INT,
  `batch_no` STRING,
  `update_time` TIMESTAMP(3),
  PRIMARY KEY (`id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'inventory',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_purchase_order` (
  `po_id` STRING,
  `line_no` INT,
  `supplier_id` STRING,
  `material_id` STRING,
  `qty` INT,
  `unit_price` DOUBLE,
  `order_date` DATE,
  `expected_date` DATE,
  `status` STRING,
  PRIMARY KEY (`po_id`, `line_no`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'purchase_order',
  'slot.name' = 'flink_purchase_order',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_purchase_order` (
  `po_id` STRING,
  `line_no` INT,
  `supplier_id` STRING,
  `material_id` STRING,
  `qty` INT,
  `unit_price` DOUBLE,
  `order_date` DATE,
  `expected_date` DATE,
  `status` STRING,
  PRIMARY KEY (`po_id`, `line_no`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'purchase_order',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_purchase_arrival` (
  `arrival_id` STRING,
  `po_id` STRING,
  `supplier_id` STRING,
  `material_id` STRING,
  `arrived_qty` INT,
  `arrival_date` DATE,
  `status` STRING,
  PRIMARY KEY (`arrival_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'purchase_arrival',
  'slot.name' = 'flink_purchase_arrival',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_purchase_arrival` (
  `arrival_id` STRING,
  `po_id` STRING,
  `supplier_id` STRING,
  `material_id` STRING,
  `arrived_qty` INT,
  `arrival_date` DATE,
  `status` STRING,
  PRIMARY KEY (`arrival_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'purchase_arrival',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_sales_order` (
  `so_id` STRING,
  `line_no` INT,
  `customer_id` STRING,
  `material_id` STRING,
  `qty` INT,
  `unit_price` DOUBLE,
  `order_date` DATE,
  `delivery_date` DATE,
  `status` STRING,
  PRIMARY KEY (`so_id`, `line_no`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'sales_order',
  'slot.name' = 'flink_sales_order',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_sales_order` (
  `so_id` STRING,
  `line_no` INT,
  `customer_id` STRING,
  `material_id` STRING,
  `qty` INT,
  `unit_price` DOUBLE,
  `order_date` DATE,
  `delivery_date` DATE,
  `status` STRING,
  PRIMARY KEY (`so_id`, `line_no`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'sales_order',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_delivery_note` (
  `delivery_id` STRING,
  `so_id` STRING,
  `customer_id` STRING,
  `material_id` STRING,
  `qty` INT,
  `delivery_date` DATE,
  `status` STRING,
  PRIMARY KEY (`delivery_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'delivery_note',
  'slot.name' = 'flink_delivery_note',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_delivery_note` (
  `delivery_id` STRING,
  `so_id` STRING,
  `customer_id` STRING,
  `material_id` STRING,
  `qty` INT,
  `delivery_date` DATE,
  `status` STRING,
  PRIMARY KEY (`delivery_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'delivery_note',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_production_order` (
  `mo_id` STRING,
  `material_id` STRING,
  `planned_qty` INT,
  `completed_qty` INT,
  `start_date` DATE,
  `due_date` DATE,
  `status` STRING,
  PRIMARY KEY (`mo_id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'production_order',
  'slot.name' = 'flink_production_order',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_production_order` (
  `mo_id` STRING,
  `material_id` STRING,
  `planned_qty` INT,
  `completed_qty` INT,
  `start_date` DATE,
  `due_date` DATE,
  `status` STRING,
  PRIMARY KEY (`mo_id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'production_order',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

CREATE TABLE `src_production_material_req` (
  `id` STRING,
  `mo_id` STRING,
  `material_id` STRING,
  `required_qty` INT,
  `issued_qty` INT,
  PRIMARY KEY (`id`) NOT ENFORCED
) WITH (
  'connector' = 'postgres-cdc',
  'hostname' = 'postgres',
  'port' = '5432',
  'username' = 'dm',
  'password' = 'dm_dev_pass',
  'database-name' = 'dm',
  'schema-name' = 'public',
  'table-name' = 'production_material_req',
  'slot.name' = 'flink_production_material_req',
  'decoding.plugin.name' = 'pgoutput',
  'scan.incremental.snapshot.enabled' = 'true'
);
CREATE TABLE `sink_production_material_req` (
  `id` STRING,
  `mo_id` STRING,
  `material_id` STRING,
  `required_qty` INT,
  `issued_qty` INT,
  PRIMARY KEY (`id`) NOT ENFORCED
) WITH (
  'connector' = 'starrocks',
  'jdbc-url' = 'jdbc:mysql://starrocks:9030',
  'load-url' = 'starrocks:8030',
  'database-name' = 'dm',
  'table-name' = 'production_material_req',
  'username' = 'root',
  'password' = '',
  'sink.semantic' = 'at-least-once',
  'sink.buffer-flush.interval-ms' = '3000'
);

EXECUTE STATEMENT SET
BEGIN
INSERT INTO `sink_company_org` SELECT * FROM `src_company_org`;
INSERT INTO `sink_department` SELECT * FROM `src_department`;
INSERT INTO `sink_employee` SELECT * FROM `src_employee`;
INSERT INTO `sink_unit` SELECT * FROM `src_unit`;
INSERT INTO `sink_material_category` SELECT * FROM `src_material_category`;
INSERT INTO `sink_material` SELECT * FROM `src_material`;
INSERT INTO `sink_unit_conversion` SELECT * FROM `src_unit_conversion`;
INSERT INTO `sink_warehouse` SELECT * FROM `src_warehouse`;
INSERT INTO `sink_storage_location` SELECT * FROM `src_storage_location`;
INSERT INTO `sink_supplier` SELECT * FROM `src_supplier`;
INSERT INTO `sink_customer` SELECT * FROM `src_customer`;
INSERT INTO `sink_dictionary` SELECT * FROM `src_dictionary`;
INSERT INTO `sink_inventory` SELECT * FROM `src_inventory`;
INSERT INTO `sink_purchase_order` SELECT * FROM `src_purchase_order`;
INSERT INTO `sink_purchase_arrival` SELECT * FROM `src_purchase_arrival`;
INSERT INTO `sink_sales_order` SELECT * FROM `src_sales_order`;
INSERT INTO `sink_delivery_note` SELECT * FROM `src_delivery_note`;
INSERT INTO `sink_production_order` SELECT * FROM `src_production_order`;
INSERT INTO `sink_production_material_req` SELECT * FROM `src_production_material_req`;
END;
