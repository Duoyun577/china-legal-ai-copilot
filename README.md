# China Legal AI Copilot

China Legal AI Copilot 是基于 Streamlit 的法律工作台。公网部署时应挂载持久化磁盘，并通过环境变量指定 SQLite 数据库位置。

家庭/朋友长期使用版支持 Google 登录白名单、按用户数据隔离、Supabase PostgreSQL 持久化、每人 API 限额和管理员可视化看板。配置及安全启用顺序见 [FAMILY_DEPLOYMENT.md](FAMILY_DEPLOYMENT.md)。所有新能力默认关闭，未配置时保持原有本地兼容模式。

## 本地运行

要求 Python 3.11 或更高版本。

```bash
python -m venv .venv
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

复制 `.env.example` 为 `.env`，按需填写 `DEEPSEEK_API_KEY`。不要提交真实密钥。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 空 | DeepSeek API 密钥；未配置时相关在线 AI 功能不可用 |
| `DATABASE_URL` | 空 | 长期部署使用的 PostgreSQL 连接字符串；为空时继续使用 SQLite |
| `FAMILY_AUTH_ENABLED` | `false` | 是否启用 Google 登录及家庭白名单 |
| `ALLOWED_USER_EMAILS` | 空 | 可登录邮箱，使用英文逗号分隔 |
| `ADMIN_USER_EMAILS` | 空 | 管理员邮箱，使用英文逗号分隔 |
| `DAILY_API_LIMIT` | `20` | 普通用户每日付费 AI 调用上限 |
| `MONTHLY_API_LIMIT` | `300` | 普通用户每月付费 AI 调用上限 |
| `MAX_UPLOAD_BYTES` | `10485760` | 单个上传文件大小上限（字节） |
| `CASE_DATABASE_PATH` | `data/cases.db` | 案件数据库路径 |
| `USAGE_DATABASE_PATH` | `data/usage.db` | 匿名使用统计数据库路径 |
| `ANALYSIS_CACHE_DATABASE_PATH` | `data/analysis_cache.db` | 分析缓存数据库路径 |
| `PORT` | 平台提供 | 公网监听端口，由 `Procfile` 传给 Streamlit |

数据库路径支持绝对路径；相对路径均以项目根目录解析。应用会自动创建数据库父目录。

## 生产部署

1. 安装 `requirements.txt`。
2. 配置环境变量和持久化磁盘，将三个数据库路径指向持久化磁盘。
3. 使用 `Procfile` 启动，或执行：

   ```bash
   streamlit run app/streamlit_app.py --server.address=0.0.0.0 --server.port=$PORT --server.headless=true
   ```

4. 反向代理应启用 WebSocket，并在网关层配置 HTTPS、访问控制和请求大小限制。法律业务数据及密钥不得写入镜像或公开日志。

### 健康检查

主进程提供同端口健康检查接口 `GET /_stcore/health`。健康响应为 HTTP 200 和 `ok`，容器或平台的 liveness/readiness probe 应指向该路径。`app.health.health_status()` 提供无副作用的应用级状态载荷，供自动化检查使用。

## 测试

```bash
python -m pytest
```
