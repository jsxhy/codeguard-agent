# CodeGuard Agent 开发说明文档

## 一、项目概述

本项目基于《智能代码审查与技术债治理 Agent 开发文档》（`1.md`）进行开发，实现了完整的 CodeGuard Agent 系统。在开发过程中，对原文档进行了仔细审阅，发现并修正了若干问题。本文档详细记录了开发实现、文档修正和调整内容。

## 二、文档问题识别与修正

### 2.1 【严重】Agent 4 闭环验证流程逻辑错误

**原文档问题：**

在编排层设计（第 4.3 节）中，LangGraph 流水线定义了如下执行流：

```
code_scan → standard_compare → refactor_suggest → verify_close_loop → generate_report
```

条件分支逻辑为：
```python
lambda state: "verify_close_loop" if state["has_refactoring"] else "generate_report"
```

这意味着：如果存在需要重构的问题（`has_refactoring=True`），则立即进入 Agent 4 闭环验证。然而，Agent 4 的职责定义（第 3.4 节）明确说明：

> "在重构 PR 提交后自动触发测试，验证改动未引入回归问题。"

**矛盾点：** Agent 3（重构建议）只是生成了重构方案，开发者尚未实际执行重构。此时直接进入 Agent 4 进行验证毫无意义——代码尚未被修改，验证什么？

**修正方案：**

1. **主审查流水线**（PR 提交触发）：`code_scan → standard_compare → refactor_suggest → generate_report`
2. **独立验证流水线**（重构 PR 提交触发）：`verify_close_loop`
3. 条件分支改为：当 `has_refactoring=True` 且 `refactored_files` 和 `refactoring_item_id` 同时存在时，才进入验证流程
4. 新增 `build_verify_pipeline()` 独立流水线，通过单独的 API 端点触发

**实现文件：** [pipeline.py](file:///d:/code/ai/智能代码审查与技术债治理Agent/codeguard-agent/app/orchestrator/pipeline.py)

### 2.2 【严重】ReviewState 类型未定义

**原文档问题：**

编排核心代码（第 4.3 节）中使用了 `StateGraph(ReviewState)`，但 `ReviewState` 从未在文档中定义。文档只定义了 `PRReviewState` 枚举，而 `ReviewState` 应该是 LangGraph 流水线中传递的状态字典类型。

**修正方案：**

在 [state.py](file:///d:/code/ai/智能代码审查与技术债治理Agent/codeguard-agent/app/orchestrator/state.py) 中定义了完整的 `ReviewState` 和 `VerifyState` TypedDict：

- `ReviewState`：主审查流水线状态，包含 pr_id、changed_files、scan_report、compliance_report、refactoring_plan 等字段
- `VerifyState`：独立验证流水线状态，包含 refactored_files、test_scope、refactoring_item_id 等字段

### 2.3 【中等】Docker Compose 版本字段已弃用

**原文档问题：**

Docker Compose 配置使用了 `version: "3.9"`，该字段在 Docker Compose V2 中已被弃用。

**修正方案：**

在 [docker-compose.yaml](file:///d:/code/ai/智能代码审查与技术债治理Agent/codeguard-agent/docker-compose.yaml) 中移除了 `version` 字段，使用现代 Compose 规范格式。

### 2.4 【中等】向量数据库选型调整

**原文档问题：**

文档指定使用 Milvus 作为向量数据库，但 Milvus 需要较重的基础设施支持（etcd、MinIO 等），对本地开发和测试不友好。

**修正方案：**

- 默认使用 **Chroma** 作为向量数据库（轻量级，支持本地持久化）
- 配置文件中保留 `vector_db.provider` 字段，支持切换为 Milvus
- Chroma 使用本地文件存储，无需额外服务

### 2.5 【中等】缺少 .env.example 文件

**原文档问题：**

配置文件中大量使用 `${ENV_VAR}` 引用环境变量，但未提供 `.env.example` 模板文件。

**修正方案：**

创建了 [.env.example](file:///d:/code/ai/智能代码审查与技术债治理Agent/codeguard-agent/.env.example)，包含所有必需的环境变量及其说明。

### 2.6 【轻微】LLM 调用缺少重试机制

**原文档问题：**

文档未提及 LLM API 调用的重试策略。在实际使用中，LLM API 可能因网络问题、速率限制等原因临时不可用。

**修正方案：**

- 在 `config.yaml` 中新增 `llm.retry_max_attempts` 和 `llm.retry_backoff_seconds` 配置
- 在 [base.py](file:///d:/code/ai/智能代码审查与技术债治理Agent/codeguard-agent/app/agents/base.py) 中实现了指数退避重试机制

### 2.7 【轻微】缺少 LLM API Base 配置

**原文档问题：**

LLM 配置只有 `api_key`，缺少 `api_base` 配置。对于使用 Azure OpenAI 或自部署模型的场景，需要自定义 API 端点。

**修正方案：**

在配置中新增 `llm.api_base` 字段，支持自定义 OpenAI 兼容 API 端点。

### 2.8 【轻微】AST 解析器复杂度计算存在 bug

**原文档问题：**

原文档的 `_estimate_complexity` 方法中，`complexity` 变量在局部赋值但从未被使用，实际复杂度计算通过 `_count_decision_points` 的引用类型参数完成，但 `_count_decision_points` 方法在 `_estimate_complexity` 中被条件判断 `hasattr` 检查，而该方法始终存在，导致逻辑混乱。

**修正方案：**

在 [ast_parser.py](file:///d:/code/ai/智能代码审查与技术债治理Agent/codeguard-agent/app/tools/ast_parser.py) 中简化了复杂度计算逻辑，使用列表引用参数传递确保正确累加。

## 三、项目结构

```
codeguard-agent/
├── app/
│   ├── main.py                     # FastAPI 入口
│   ├── config.py                   # 配置加载（支持 YAML + 环境变量）
│   ├── api/
│   │   ├── webhook.py              # Webhook 接收端点
│   │   ├── reviews.py              # 审查报告 API
│   │   └── debt.py                 # 技术债管理 API
│   ├── agents/
│   │   ├── base.py                 # Agent 基类（含重试机制）
│   │   ├── code_scan_agent.py      # Agent 1：代码扫描
│   │   ├── standard_compare_agent.py  # Agent 2：规范比对
│   │   ├── refactor_agent.py       # Agent 3：重构建议
│   │   └── verify_agent.py         # Agent 4：闭环验证
│   ├── orchestrator/
│   │   ├── pipeline.py             # LangGraph 编排（含独立验证流水线）
│   │   └── state.py                # 状态管理（ReviewState + VerifyState）
│   ├── tools/
│   │   ├── git_client.py           # Git API 封装（GitLab/GitHub）
│   │   ├── semgrep_runner.py       # Semgrep 静态分析集成
│   │   ├── ast_parser.py           # Tree-sitter AST 解析
│   │   └── test_runner.py          # 测试执行器
│   ├── models/
│   │   ├── database.py             # SQLAlchemy 异步数据库
│   │   ├── schemas.py              # ORM 数据模型
│   │   └── vector_store.py         # Chroma 向量数据库
│   └── utils/
│       ├── token_counter.py        # Token 消耗统计
│       └── notification.py         # 通知推送（Slack/Email）
├── frontend/                       # React + Ant Design 前端
│   ├── src/
│   │   ├── App.tsx                 # 主应用布局
│   │   ├── main.tsx                # 入口
│   │   └── pages/
│   │       ├── Dashboard.tsx       # 总览看板
│   │       ├── ReviewDetail.tsx    # 审查详情
│   │       └── DebtBoard.tsx       # 技术债看板
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── standards/                      # 规范文档
│   ├── coding-guide-v2.3.md
│   ├── architecture-v2.3.md
│   └── api-design-v1.5.md
├── prompts/                        # Prompt 模板
│   ├── scan_prompt.txt
│   ├── compare_prompt.txt
│   ├── refactor_prompt.txt
│   └── verify_prompt.txt
├── tests/                          # 单元测试
│   ├── test_ast_parser.py
│   ├── test_agents.py
│   ├── test_state.py
│   ├── test_token_counter.py
│   └── test_config.py
├── docker-compose.yaml
├── Dockerfile
├── config.yaml
├── requirements.txt
├── .env.example
└── pytest.ini
```

## 四、核心实现说明

### 4.1 Agent 架构

所有 Agent 继承自 `BaseAgent`，具备以下能力：
- **LLM 调用**：通过 LangChain 的 ChatOpenAI 接口
- **重试机制**：指数退避重试，可配置重试次数和间隔
- **超时控制**：每个 Agent 有独立的超时时间
- **JSON 提取**：自动从 LLM 响应中提取 JSON 内容
- **执行追踪**：记录执行时间、状态等元信息

### 4.2 编排流水线

采用 LangGraph 的 `StateGraph` 实现两条独立流水线：

1. **主审查流水线**（`build_review_pipeline`）：
   - 触发条件：PR Webhook 事件
   - 流程：code_scan → standard_compare → refactor_suggest → generate_report
   - 如果存在重构项且提供了重构文件信息，可选进入 verify_close_loop

2. **独立验证流水线**（`build_verify_pipeline`）：
   - 触发条件：重构 PR 提交
   - 流程：verify → END

### 4.3 配置管理

采用 YAML + 环境变量的双层配置策略：
- `config.yaml`：定义所有配置项及其默认值
- 环境变量：覆盖敏感信息（API Key、数据库密码等）
- Pydantic Settings：类型安全的配置访问

### 4.4 向量数据库

使用 Chroma 替代 Milvus：
- 支持本地持久化存储
- 无需额外基础设施
- API 兼容，可随时切换回 Milvus
- 支持规范文档和代码片段的语义检索

## 五、与原文档的差异总结

| 项目 | 原文档 | 实际实现 | 修正原因 |
|------|--------|----------|----------|
| Agent 4 流程 | 紧跟 Agent 3 执行 | 独立流水线，按需触发 | 逻辑矛盾：重构尚未执行无法验证 |
| ReviewState | 未定义 | TypedDict 完整定义 | LangGraph 必需的状态类型 |
| 向量数据库 | Milvus | Chroma（可切换） | 降低本地开发复杂度 |
| Docker Compose | version: "3.9" | 移除 version 字段 | V2 规范已弃用该字段 |
| LLM 重试 | 未提及 | 指数退避重试 | 提升系统可靠性 |
| API Base | 未配置 | 支持自定义端点 | 兼容 Azure/自部署模型 |
| .env 模板 | 未提供 | .env.example | 便于开发者快速上手 |

## 六、启动方式

### 6.1 本地开发

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际配置

# 3. 启动 PostgreSQL 和 Redis
docker compose up -d postgres redis

# 4. 启动后端
uvicorn app.main:app --reload --port 8000

# 5. 启动前端
cd frontend
npm install
npm run dev
```

### 6.2 Docker 部署

```bash
docker compose up -d
```

访问：
- 后端 API：http://localhost:8000/docs
- 前端看板：http://localhost:3000
