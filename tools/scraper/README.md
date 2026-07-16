# FIFA Player Data Import

## Data Sources

推荐的免费数据集（任选一个）：

1. **Kaggle FIFA 23 Dataset**
   https://www.kaggle.com/datasets/bryanb/fifa-player-stats-database
   → 下载 `FIFA23_official_data.csv`

2. **GitHub FIFA Dataset**
   https://github.com/amanthedorkknight/fifa18-player-data
   → 下载 `complete.csv`

3. **SoFIFA 直接爬取**
   使用 `so_fifa_scraper.py`（需要 requests + beautifulsoup4）

## 导入命令

```bash
cd tools/scraper
pip install pandas requests

# 从 CSV 导入
python import_fifa_data.py --csv ~/Downloads/FIFA23_official_data.csv

# 或从 SoFIFA 爬取（慢，需要代理）
python so_fifa_scraper.py --leagues "Premier League,La Liga" --max-teams 10
```

输出文件在 `frontend/public/data/teams/` 下：
```
teams/
├── index.json              # 所有队伍列表
├── club/
│   ├── FC_Barcelona.json
│   ├── Real_Madrid.json
│   └── ...
└── nation/
    ├── France.json
    ├── Brazil.json
    └── ...
```

## 数据格式

```json
{
  "name": "FC Barcelona",
  "type": "club",
  "players": [
    {
      "name": "Robert Lewandowski",
      "position": "ST",
      "overall": 91,
      "attributes": {
        "pace": 75, "shooting": 92, "passing": 80,
        "dribbling": 86, "defending": 35, "physicality": 77,
        "stamina": 75, "awareness": 91, "composure": 92
      }
    }
  ]
}
```
