SET 'execution.checkpointing.interval' = '5s';
SET 'pipeline.name' = 'dm-cdc-pg-to-starrocks';

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

EXECUTE STATEMENT SET
BEGIN
INSERT INTO `sink_inventory` SELECT * FROM `src_inventory`;
END;
