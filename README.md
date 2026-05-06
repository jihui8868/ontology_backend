# 数据库故障分析系统 - 后端

基于本体技术和多智能体框架的数据库故障根因分析系统后端服务。

## 功能概览

- 日志上传与自动格式识别（PostgreSQL / MySQL）
- 多智能体流水线：日志解析 → 本体查询 → 案例检索 → 推理 → 报告生成
- Neo4j 知识图谱支持（PostgreSQL & MySQL 本体预加载）
- Milvus 向量库支持（历史案例相似度检索）
- 结构化 JSON 报告与 Markdown 输出

## 项目结构

```
backend/
├── main.py                      # FastAPI 应用入口
├── pyproject.toml               # 项目配置与依赖
├── .env / .env.example          # 环境变量配置
│
└── app/
    ├── core/
    │   ├── config.py            # Pydantic Settings 配置
    │   └── storage.py           # 文件存储管理
    │
    ├── db/
    │   ├── neo4j_client.py      # Neo4j 异步客户端
    │   └── milvus_client.py     # Milvus 客户端
    │
    ├── ontology/
    │   ├── schema.py            # 本体 Pydantic 模型
    │   └── seed/
    │       ├── postgres.cypher  # PostgreSQL 本体初始数据
    │       └── mysql.cypher     # MySQL 本体初始数据
    │
    ├── models/
    │   ├── analysis.py          # 分析请求/响应模型
    │   └── report.py            # 报告模型
    │
    ├── api/
    │   └── routes/
    │       ├── analysis.py      # 分析接口（上传、报告、状态）
    │       └── history.py       # 历史记录接口
    │
    ├── services/
    │   └── analysis_service.py  # 业务逻辑服务
    │
    └── agents/
        ├── log_parser.py        # [待实现] 日志解析 Agent
        ├── ontology_query.py    # [待实现] 本体查询 Agent
        ├── similar_case.py      # [待实现] 相似案例检索 Agent
        ├── reasoning.py         # [待实现] 推理 Agent
        ├── report.py            # [待实现] 报告生成 Agent
        └── pipeline.py          # [待实现] DeepAgents 编排
```

## 安装与运行

### 前置要求

- Python 3.13+
- Neo4j 服务 (默认 bolt://localhost:7687)
- Milvus 服务 (默认 localhost:19530)

### 安装依赖

```bash
cd backend
uv sync
```

### 配置环境

复制 `.env.example` 为 `.env` 并填写必要的配置：

```bash
cp .env.example .env
```

必需的配置项：
- `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD`
- `MILVUS_HOST` / `MILVUS_PORT`
- `ANTHROPIC_API_KEY` (用于 Claude LLM)

### 启动服务

```bash
uv run python main.py
```

服务会在 `http://localhost:8000` 启动，API 文档在 `/docs`。

## API 端点

### 分析接口

#### POST `/api/analysis/upload`
上传日志文件并触发分析

**请求**：
```bash
curl -X POST "http://localhost:8000/api/analysis/upload" \
  -F "file=@error.log"
```

**响应**：
```json
{
  "analysis_id": "uuid",
  "status": "queued",
  "db_type": "postgresql"
}
```

#### GET `/api/analysis/{analysis_id}/status`
查询分析进度（SSE 流式推送）

```bash
curl -N "http://localhost:8000/api/analysis/{id}/status"
```

#### GET `/api/analysis/{analysis_id}/report`
获取分析报告

```bash
curl "http://localhost:8000/api/analysis/{id}/report"
```

### 历史接口

#### GET `/api/analysis/history`
获取历史分析列表

```bash
curl "http://localhost:8000/api/analysis/history?db_type=postgresql&skip=0&limit=20"
```

#### DELETE `/api/analysis/history/{analysis_id}`
删除历史记录

## 技术栈

- **Web Framework**: FastAPI 0.115+
- **ASGI Server**: Uvicorn 0.34+
- **Graph Database**: Neo4j 5.28+
- **Vector Database**: Milvus 2.5+
- **LLM**: Anthropic Claude via langchain-anthropic
- **Agent Framework**: DeepAgents 0.5.7+
- **Configuration**: Pydantic Settings 2.0+

## 开发状态

### Phase 1 ✓ 完成
- [x] FastAPI 应用骨架
- [x] 环境配置系统（Pydantic Settings）
- [x] Neo4j 客户端与 Cypher 操作
- [x] Milvus 客户端与向量检索
- [x] PostgreSQL & MySQL 本体种子数据
- [x] API 路由框架与模型定义
- [x] 文件存储管理

### Phase 2 待实现
- [ ] 5 个 Agent 实现（LogParser, OntologyQuery, SimilarCase, Reasoning, Report）
- [ ] DeepAgents 任务图编排
- [ ] SSE 进度推送

### Phase 3 待实现
- [ ] 完整的分析流水线集成
- [ ] 异步任务后台执行

## 常见问题

### Q: 如何连接到本地 Neo4j？

确保 Neo4j 运行在默认端口 7687，或在 `.env` 中修改 `NEO4J_URI`。

### Q: Milvus 连接失败怎么办？

检查 Milvus 服务是否在 `localhost:19530` 运行。使用 Docker 快速启动：

```bash
docker run -d --name milvus -p 19530:19530 milvusdb/milvus:latest
```

### Q: ANTHROPIC_API_KEY 如何获取？

访问 [Anthropic Console](https://console.anthropic.com) 生成 API 密钥。

## 贡献

欢迎提交 Issue 或 Pull Request！

## 许可证

MIT License
