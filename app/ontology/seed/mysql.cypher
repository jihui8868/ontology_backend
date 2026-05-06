// MySQL 本体知识图谱初始数据

// ============ ErrorCode 节点 ============
CREATE (e1:ErrorCode {code: '1213', description: 'Deadlock found when trying to get lock', db: 'mysql'});
CREATE (e2:ErrorCode {code: '1040', description: 'Too many connections', db: 'mysql'});
CREATE (e3:ErrorCode {code: '2002', description: 'Cannot connect to MySQL server', db: 'mysql'});
CREATE (e4:ErrorCode {code: '1317', description: 'Query execution was interrupted', db: 'mysql'});
CREATE (e5:ErrorCode {code: '1114', description: 'Table is full', db: 'mysql'});
CREATE (e6:ErrorCode {code: '1030', description: 'Got error from storage engine', db: 'mysql'});
CREATE (e7:ErrorCode {code: '1205', description: 'Lock wait timeout exceeded', db: 'mysql'});

// ============ FaultType 节点 ============
CREATE (f1:FaultType {name: 'Deadlock', component: 'InnoDB', db: 'mysql'});
CREATE (f2:FaultType {name: 'ConnectionExhaustion', component: 'ConnectionPool', db: 'mysql'});
CREATE (f3:FaultType {name: 'DiskFull', component: 'Storage', db: 'mysql'});
CREATE (f4:FaultType {name: 'LockTimeout', component: 'LockManager', db: 'mysql'});
CREATE (f5:FaultType {name: 'TableCorruption', component: 'StorageEngine', db: 'mysql'});

// ============ RootCause 节点 ============
CREATE (r1:RootCause {name: 'LongRunningTransaction'});
CREATE (r2:RootCause {name: 'LockWaitTimeout'});
CREATE (r3:RootCause {name: 'ConnectionLeak'});
CREATE (r4:RootCause {name: 'DiskSpaceExhausted'});
CREATE (r5:RootCause {name: 'InnoDBBufferPoolExhaustion'});
CREATE (r6:RootCause {name: 'UncleanShutdown'});

// ============ Symptom 节点 ============
CREATE (s1:Symptom {name: 'SlowQuery'});
CREATE (s2:Symptom {name: 'QueryTimeout'});
CREATE (s3:Symptom {name: 'ConnectionRefused'});
CREATE (s4:Symptom {name: 'ReplicationLag'});
CREATE (s5:Symptom {name: 'HighCPUUsage'});
CREATE (s6:Symptom {name: 'TableLocked'});
CREATE (s7:Symptom {name: 'WriteBlocked'});

// ============ Resolution 节点 ============
CREATE (res1:Resolution {action: 'Kill blocking queries', detail: 'KILL CONNECTION thread_id'});
CREATE (res2:Resolution {action: 'Increase max_connections', detail: 'SET GLOBAL max_connections = 500'});
CREATE (res3:Resolution {action: 'Increase innodb_buffer_pool_size', detail: 'Restart MySQL with updated parameter'});
CREATE (res4:Resolution {action: 'Increase innodb_lock_wait_timeout', detail: 'SET GLOBAL innodb_lock_wait_timeout = 50'});
CREATE (res5:Resolution {action: 'Cleanup temporary files', detail: 'Remove old tmp files'});
CREATE (res6:Resolution {action: 'Check table', detail: 'CHECK TABLE table_name'});

// ============ 关系：ErrorCode -> FaultType ============
MATCH (e:ErrorCode {code: '1213'}), (f:FaultType {name: 'Deadlock'})
CREATE (e)-[:BELONGS_TO]->(f);

MATCH (e:ErrorCode {code: '1040'}), (f:FaultType {name: 'ConnectionExhaustion'})
CREATE (e)-[:BELONGS_TO]->(f);

MATCH (e:ErrorCode {code: '1114'}), (f:FaultType {name: 'DiskFull'})
CREATE (e)-[:BELONGS_TO]->(f);

MATCH (e:ErrorCode {code: '1205'}), (f:FaultType {name: 'LockTimeout'})
CREATE (e)-[:BELONGS_TO]->(f);

// ============ 关系：FaultType -> RootCause ============
MATCH (f:FaultType {name: 'Deadlock'}), (rc:RootCause {name: 'LongRunningTransaction'})
CREATE (f)-[:CAUSED_BY]->(rc);

MATCH (f:FaultType {name: 'Deadlock'}), (rc:RootCause {name: 'LockWaitTimeout'})
CREATE (f)-[:CAUSED_BY]->(rc);

MATCH (f:FaultType {name: 'ConnectionExhaustion'}), (rc:RootCause {name: 'ConnectionLeak'})
CREATE (f)-[:CAUSED_BY]->(rc);

MATCH (f:FaultType {name: 'DiskFull'}), (rc:RootCause {name: 'DiskSpaceExhausted'})
CREATE (f)-[:CAUSED_BY]->(rc);

MATCH (f:FaultType {name: 'LockTimeout'}), (rc:RootCause {name: 'InnoDBBufferPoolExhaustion'})
CREATE (f)-[:CAUSED_BY]->(rc);

MATCH (f:FaultType {name: 'TableCorruption'}), (rc:RootCause {name: 'UncleanShutdown'})
CREATE (f)-[:CAUSED_BY]->(rc);

// ============ 关系：FaultType -> Symptom ============
MATCH (f:FaultType {name: 'Deadlock'}), (s:Symptom {name: 'QueryTimeout'})
CREATE (f)-[:MANIFESTS_AS]->(s);

MATCH (f:FaultType {name: 'ConnectionExhaustion'}), (s:Symptom {name: 'ConnectionRefused'})
CREATE (f)-[:MANIFESTS_AS]->(s);

MATCH (f:FaultType {name: 'DiskFull'}), (s:Symptom {name: 'WriteBlocked'})
CREATE (f)-[:MANIFESTS_AS]->(s);

MATCH (f:FaultType {name: 'LockTimeout'}), (s:Symptom {name: 'TableLocked'})
CREATE (f)-[:MANIFESTS_AS]->(s);

// ============ 关系：FaultType -> Resolution ============
MATCH (f:FaultType {name: 'Deadlock'}), (res:Resolution {action: 'Kill blocking queries'})
CREATE (f)-[:RESOLVED_BY]->(res);

MATCH (f:FaultType {name: 'ConnectionExhaustion'}), (res:Resolution {action: 'Increase max_connections'})
CREATE (f)-[:RESOLVED_BY]->(res);

MATCH (f:FaultType {name: 'DiskFull'}), (res:Resolution {action: 'Cleanup temporary files'})
CREATE (f)-[:RESOLVED_BY]->(res);

MATCH (f:FaultType {name: 'LockTimeout'}), (res:Resolution {action: 'Increase innodb_lock_wait_timeout'})
CREATE (f)-[:RESOLVED_BY]->(res);

MATCH (f:FaultType {name: 'TableCorruption'}), (res:Resolution {action: 'Check table'})
CREATE (f)-[:RESOLVED_BY]->(res);

// ============ 关系：FaultType -> FaultType (Related) ============
MATCH (f1:FaultType {name: 'Deadlock'}), (f2:FaultType {name: 'LockTimeout'})
CREATE (f1)-[:RELATED_TO]->(f2);

MATCH (f1:FaultType {name: 'DiskFull'}), (f2:FaultType {name: 'TableCorruption'})
CREATE (f1)-[:RELATED_TO]->(f2);
