# 后端编码规范 v2.3

## 1. 命名规范

### 1.1 变量与函数
- 使用 snake_case 命名：`get_user_info`、`total_count`
- 布尔变量使用 is/has/can 前缀：`is_active`、`has_permission`

### 1.2 类名
- 使用 PascalCase 命名：`UserService`、`AuthController`
- 异常类以 Error 结尾：`ValidationError`

### 1.3 常量
- 使用 UPPER_SNAKE_CASE：`MAX_RETRIES`、`DEFAULT_TIMEOUT`

### 1.4 模块与包
- 使用小写字母，不加下划线：`userservice`、`auth`

## 2. 函数规范

### 2.1 函数长度
- 单个函数不超过 50 行
- 圈复杂度不超过 10
- 参数数量不超过 5 个，超过时使用参数对象

### 2.2 函数文档
- 公共函数必须包含 docstring
- 使用 Google 风格 docstring

## 3. 分层架构规范

### 3.1 依赖方向
- Controller → Service → Repository → Model
- 禁止跨层直接调用（如 Repository 直接调用 Controller）
- 禁止反向依赖（如 Model 依赖 Service）

### 3.2 各层职责
- **Controller**: 接收请求、参数校验、返回响应
- **Service**: 业务逻辑编排、事务管理
- **Repository**: 数据访问、ORM 操作
- **Model**: 数据模型定义

## 4. 安全规范

### 4.1 密钥管理
- 禁止硬编码密钥、密码
- 使用环境变量或密钥管理服务
- .env 文件不得提交至版本控制

### 4.2 输入校验
- 所有外部输入必须校验
- 使用 Pydantic 模型进行类型校验
- 防范 SQL 注入：使用参数化查询

## 5. 依赖管理

### 5.1 禁止使用的库
- `pickle`：存在反序列化安全风险
- `marshal`：不安全的序列化
- `subprocess`（非必要场景）：存在命令注入风险
- `eval` / `exec`：存在代码注入风险

### 5.2 版本约束
- requirements.txt 中必须锁定版本号
- 定期更新依赖，修复安全漏洞
