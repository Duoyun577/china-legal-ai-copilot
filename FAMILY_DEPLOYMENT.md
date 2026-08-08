# 家庭长期使用部署

本版本采用可开关部署。未配置新变量时继续使用原 SQLite 和匿名兼容模式；只有明确设置后才启用家庭登录和 Supabase PostgreSQL。

## 1. 创建 Supabase 项目

1. 在 Supabase 创建项目。
2. 在项目的数据库连接设置中复制 PostgreSQL pooler 连接字符串。
3. 将连接字符串保存为 Streamlit Secrets 根级变量 `DATABASE_URL`。密码中的特殊字符必须进行 URL 编码，并保留 `sslmode=require`。
4. 第一次启动应用后，在 Supabase Table Editor 中应能看到 `cases`、`case_records`、`case_files`、`case_events`、`case_memories`、`analysis_cache`、`usage_events` 和 `user_profiles`。
5. 在 Supabase SQL Editor 运行 `config/supabase_hardening.sql`，关闭 Data API 对家庭法律数据的访问。

不要把数据库密码、service role key 或真实 `secrets.toml` 提交到 GitHub。

## 2. 配置 Google 登录

1. 在 Google Cloud Console 创建 OAuth Web Client。
2. Authorized redirect URI 设置为：

   `https://china-legal-ai-copilot-gatttcxhnxrdakyccb85mm.streamlit.app/oauth2callback`

3. 将 Client ID、Client Secret、随机生成的 Cookie Secret 写入 Streamlit Secrets 的 `[auth]`。
4. `ALLOWED_USER_EMAILS` 只填写允许使用网站的家庭成员邮箱；`ADMIN_USER_EMAILS` 只填写管理员邮箱。

## 3. API 限额

- `DAILY_API_LIMIT`：普通用户每天允许的付费 AI 操作次数，默认 20。
- `MONTHLY_API_LIMIT`：普通用户每月允许的付费 AI 操作次数，默认 300。
- 管理员账号可查看首页底部的数据看板，并豁免普通额度。
- 失败的 API 请求同样计入额度，避免通过失败重试无限消耗资源。

## 4. 安全启用顺序

1. 先配置 `DATABASE_URL`，保持 `FAMILY_AUTH_ENABLED = false`，确认数据库连接和页面正常。
2. 在 Supabase 运行加固 SQL。
3. 配置 Google OAuth、白名单和管理员邮箱。
4. 最后设置 `FAMILY_AUTH_ENABLED = true` 并重启应用。
5. 使用管理员账号和一个普通家庭账号分别验证：只能看到自己的案件和文件，普通用户能看到自己的剩余额度。

如果配置异常，可立即将 `FAMILY_AUTH_ENABLED` 改为 `false`，并暂时移除 `DATABASE_URL`，应用会回到原 SQLite 兼容模式。不要删除 Supabase 项目，远端数据会保留。
