// PostgreSQL 本体知识图谱初始数据

// ============ ErrorCode 节点 ============
CREATE (e1:ErrorCode {code: '40P01', description: 'deadlock detected', db: 'postgresql'});
CREATE (e2:ErrorCode {code: '53300', description: 'too many connections', db: 'postgresql'});
CREATE (e3:ErrorCode {code: '57P03', description: 'cannot connect now - server is in recovery mode', db: 'postgresql'});
CREATE (e4:ErrorCode {code: '54000', description: 'out of memory', db: 'postgresql'});
CREATE (e5:ErrorCode {code: '42P01', description: 'undefined table', db: 'postgresql'});
CREATE (e6:ErrorCode {code: 'XX000', description: 'internal error', db: 'postgresql'});
CREATE (e7:ErrorCode {code: '08000', description: 'connection failure', db: 'postgresql'});

// ============ FaultType 节点 ============
CREATE (f1:FaultType {name: 'Deadlock', component: 'LockManager', db: 'postgresql'});
CREATE (f2:FaultType {name: 'ConnectionExhaustion', component: 'ConnectionPool', db: 'postgresql'});
CREATE (f3:FaultType {name: 'OOM', component: 'Memory', db: 'postgresql'});
CREATE (f4:FaultType {name: 'CrashRecovery', component: 'WAL', db: 'postgresql'});
CREATE (f5:FaultType {name: 'CorruptedIndex', component: 'IndexManager', db: 'postgresql'});

// ============ RootCause 节点 ============
CREATE (r1:RootCause {name: 'LongRunningTransaction'});
CREATE (r2:RootCause {name: 'CircularLockWait'});
CREATE (r3:RootCause {name: 'ConnectionLeak'});
CREATE (r4:RootCause {name: 'MemoryLeak'});
CREATE (r5:RootCause {name: 'UnexpectedServerCrash'});
CREATE (r6:RootCause {name: 'DiskFull'});
CREATE (r7:RootCause {name: 'IndexFragmentation'});

// ============ Symptom 节点 ============
CREATE (s1:Symptom {name: 'SlowQuery'});
CREATE (s2:Symptom {name: 'QueryTimeout'});
CREATE (s3:Symptom {name: 'ConnectionRefused'});
CREATE (s4:Symptom {name: 'ReplicationLag'});
CREATE (s5:Symptom {name: 'HighCPUUsage'});
CREATE (s6:Symptom {name: 'ServerCrash'});

// ============ Resolution 节点 ============
CREATE (res1:Resolution {action: 'Kill blocking queries', detail: 'SELECT pg_terminate_backend(pid) FROM pg_stat_activity'});
CREATE (res2:Resolution {action: 'Increase max_connections', detail: 'ALTER SYSTEM SET max_connections = 300'});
CREATE (res3:Resolution {action: 'Increase work_mem', detail: 'ALTER SYSTEM SET work_mem = 256MB'});
CREATE (res4:Resolution {action: 'REINDEX', detail: 'REINDEX TABLE table_name'});
CREATE (res5:Resolution {action: 'Clear cache', detail: 'DISCARD PLANS'});

// ============ 关系：ErrorCode -> FaultType ============
MATCH (e:ErrorCode {code: '40P01'}), (f:FaultType {name: 'Deadlock'})
CREATE (e)-[:BELONGS_TO]->(f);

MATCH (e:ErrorCode {code: '53300'}), (f:FaultType {name: 'ConnectionExhaustion'})
CREATE (e)-[:BELONGS_TO]->(f);

MATCH (e:ErrorCode {code: '54000'}), (f:FaultType {name: 'OOM'})
CREATE (e)-[:BELONGS_TO]->(f);

MATCH (e:ErrorCode {code: '57P03'}), (f:FaultType {name: 'CrashRecovery'})
CREATE (e)-[:BELONGS_TO]->(f);

// ============ 关系：FaultType -> RootCause ============
MATCH (f:FaultType {name: 'Deadlock'}), (rc:RootCause {name: 'LongRunningTransaction'})
CREATE (f)-[:CAUSED_BY]->(rc);

MATCH (f:FaultType {name: 'Deadlock'}), (rc:RootCause {name: 'CircularLockWait'})
CREATE (f)-[:CAUSED_BY]->(rc);

MATCH (f:FaultType {name: 'ConnectionExhaustion'}), (rc:RootCause {name: 'ConnectionLeak'})
CREATE (f)-[:CAUSED_BY]->(rc);

MATCH (f:FaultType {name: 'OOM'}), (rc:RootCause {name: 'MemoryLeak'})
CREATE (f)-[:CAUSED_BY]->(rc);

MATCH (f:FaultType {name: 'CrashRecovery'}), (rc:RootCause {name: 'UnexpectedServerCrash'})
CREATE (f)-[:CAUSED_BY]->(rc);

MATCH (f:FaultType {name: 'CorruptedIndex'}), (rc:RootCause {name: 'IndexFragmentation'})
CREATE (f)-[:CAUSED_BY]->(rc);

// ============ 关系：FaultType -> Symptom ============
MATCH (f:FaultType {name: 'Deadlock'}), (s:Symptom {name: 'QueryTimeout'})
CREATE (f)-[:MANIFESTS_AS]->(s);

MATCH (f:FaultType {name: 'ConnectionExhaustion'}), (s:Symptom {name: 'ConnectionRefused'})
CREATE (f)-[:MANIFESTS_AS]->(s);

MATCH (f:FaultType {name: 'OOM'}), (s:Symptom {name: 'HighCPUUsage'})
CREATE (f)-[:MANIFESTS_AS]->(s);

MATCH (f:FaultType {name: 'CrashRecovery'}), (s:Symptom {name: 'ServerCrash'})
CREATE (f)-[:MANIFESTS_AS]->(s);

// ============ 关系：FaultType -> Resolution ============
MATCH (f:FaultType {name: 'Deadlock'}), (res:Resolution {action: 'Kill blocking queries'})
CREATE (f)-[:RESOLVED_BY]->(res);

MATCH (f:FaultType {name: 'ConnectionExhaustion'}), (res:Resolution {action: 'Increase max_connections'})
CREATE (f)-[:RESOLVED_BY]->(res);

MATCH (f:FaultType {name: 'OOM'}), (res:Resolution {action: 'Increase work_mem'})
CREATE (f)-[:RESOLVED_BY]->(res);

MATCH (f:FaultType {name: 'CorruptedIndex'}), (res:Resolution {action: 'REINDEX'})
CREATE (f)-[:RESOLVED_BY]->(res);

// ============ 关系：FaultType -> FaultType (Related) ============
MATCH (f1:FaultType {name: 'Deadlock'}), (f2:FaultType {name: 'CrashRecovery'})
CREATE (f1)-[:RELATED_TO]->(f2);

MATCH (f1:FaultType {name: 'OOM'}), (f2:FaultType {name: 'CrashRecovery'})
CREATE (f1)-[:RELATED_TO]->(f2);
