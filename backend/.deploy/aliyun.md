# Deploy Backend to Alibaba Cloud FC (函数计算)

## Architecture

```
Vercel (Frontend) → FC (FastAPI) → Supabase (PostgreSQL)
   免费               免费额度        500MB 免费
```

FC 免费额度：每月 100 万次调用 / 40 万 CU-s，MVP 完全够用。

## Step 1: Install FC CLI

```bash
npm install -g @alicloud/fun
fun config   # 按提示配置 AccessKey
```

## Step 2: Deploy

```bash
cd backend
fun deploy
```

`template.yml` 已配好，会自动上传代码、安装依赖、创建 HTTP 触发器。

部署完成后 FC 会返回一个公网 URL：`https://xxx.cn-hangzhou.fc.aliyuncs.com/`

## Step 3: Set up Supabase

1. [supabase.com](https://supabase.com) → New Project
2. Settings → Database → Connection String → URI 格式
3. 在 FC 控制台设置环境变量：

```
DATABASE_URL = postgresql://user:pass@db.xxxx.supabase.co:5432/postgres
TRY1000_JWT_SECRET_KEY = <随机字符串>
```

## Step 4: Update Frontend

Vercel 后台设置 `NEXT_PUBLIC_API_URL` = FC 公网 URL + `/api/v1`

---

## Local Dev

```bash
cd backend
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload
# SQLite 自动创建，无需 PostgreSQL
```
