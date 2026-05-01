# 后端架构规范 v2.3

## 1. 整体架构

### 1.1 分层架构
采用经典的三层架构模式：

```
Controller (API 层)
    ↓
Service (业务逻辑层)
    ↓
Repository (数据访问层)
```

### 1.2 模块划分
- 按业务领域划分模块：auth、user、order、payment
- 每个模块包含完整的分层结构
- 模块间通过 Service 接口通信

## 2. 依赖规则

### 2.1 允许的依赖方向
- Controller 可以依赖 Service
- Service 可以依赖 Repository
- Service 可以依赖其他 Service
- Repository 可以依赖 Model

### 2.2 禁止的依赖方向
- Repository 不得直接依赖 Controller
- Model 不得依赖 Service 或 Controller
- 禁止循环依赖

### 2.3 跨模块调用
- 跨模块调用必须通过 Service 层
- 禁止直接导入其他模块的 Repository

## 3. API 设计规范

### 3.1 RESTful 标准
- 路径使用小写 kebab-case：`/api/v1/user-profiles`
- 正确使用 HTTP 方法：GET 查询、POST 创建、PUT 更新、DELETE 删除
- 使用复数名词作为资源名：`/users` 而非 `/user`

### 3.2 错误码规范
- 400：请求参数错误
- 401：未认证
- 403：无权限
- 404：资源不存在
- 500：服务器内部错误

### 3.3 响应格式
```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

## 4. 数据库规范

### 4.1 表命名
- 使用 snake_case：`user_profile`
- 关联表使用两个实体名：`user_role`

### 4.2 字段命名
- 主键统一使用 `id`
- 外键使用 `实体名_id`：`user_id`
- 时间字段：`created_at`、`updated_at`
