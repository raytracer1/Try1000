# Deploy Backend to Alibaba Cloud FC

## Step 1: Install Serverless Devs

```bash
npm install -g @serverless-devs/s
s config add --AccessKeyID <AK> --AccessKeySecret <SK> -a default
```

## Step 2: Deploy

```bash
cd backend
s deploy
```

`s` 会自动上传代码、安装依赖、创建 HTTP 触发器。

## Step 3: 环境变量（FC 控制台）

| 变量 | |
|------|---|
| `DATABASE_URL` | Supabase PostgreSQL |
| `TRY1000_JWT_SECRET_KEY` | 随机 64 位 |
| `TRY1000_GOOGLE_CLIENT_ID` | Google OAuth |
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_SERVICE_KEY` | Supabase secret key |

## Step 4: 首次 seed

FC 控制台 → 函数详情 → 在线执行：
```python
from server.database import init_db; init_db()
from seed import seed; seed()
```
