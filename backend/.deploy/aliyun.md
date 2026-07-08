# Deploy Backend to Alibaba Cloud FC (函数计算)

## Architecture

```
Vercel (Frontend) → FC Serverless (FastAPI) → Supabase (PostgreSQL)
      免费               免费额度                 500MB 免费
```

FC 免费额度：每月 100 万次调用 / 40 万 CU-s。

## Step 1: 安装 FC CLI

```bash
npm install -g @alicloud/fun
fun config   # 按提示配置阿里云 AccessKey
```

## Step 2: 部署

```bash
cd backend
fun deploy
```

`template.yml` 已配置好，会自动上传代码、安装依赖。

部署完成后 FC 控制台会显示公网 URL：`https://xxx.cn-hangzhou.fc.aliyuncs.com`

## Step 3: 配置 Supabase 数据库

1. [supabase.com](https://supabase.com) → New Project → 记下密码
2. Settings → Database → Connection String → URI → 复制
3. 在 FC 控制台 → 函数详情 → 环境变量 → 添加：

```
DATABASE_URL = postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres
```

## Step 4: 配置环境变量

FC 控制台 → 环境变量 → 添加：

| 变量 | 必须 | 说明 |
|------|------|------|
| `DATABASE_URL` | ✅ | Supabase PostgreSQL 连接串 |
| `TRY1000_JWT_SECRET_KEY` | ✅ | 随机字符串，JWT 签名用 |
| `TRY1000_GOOGLE_CLIENT_ID` | ✅ | Google OAuth 客户端 ID |
| `SUPABASE_URL` | ❌ | Supabase Storage 地址 |
| `SUPABASE_SERVICE_KEY` | ❌ | Supabase Storage 密钥 |
| `TRY1000_ABLY_API_KEY` | ❌ | Ably key（Engine 唤醒用） |

```bash
# 生成随机 JWT key
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Step 5: 部署前端

Vercel 后台 → Settings → Environment Variables：

```
NEXT_PUBLIC_API_URL = https://xxx.cn-hangzhou.fc.aliyuncs.com
NEXT_PUBLIC_GOOGLE_CLIENT_ID = xxxxx.apps.googleusercontent.com
```

## Step 6: 首次运行

部署后 FC 自动执行 `init_db()` 建表。然后手动 seed：

```bash
# 在 FC 控制台 → 函数详情 → 在线执行，运行：
python -c "from server.database import init_db; init_db(); from seed import seed; seed()"
```

---

## 本地开发

```bash
cd backend
pip install -r requirements.txt
python seed.py
uvicorn server.main:app --reload    # SQLite 自动创建
```
