#!/bin/bash
# Download FIFA player dataset from GitHub and import
set -e

CSV_URL="https://raw.githubusercontent.com/prashantghimire/sofifa-web-scraper/main/player_stats.csv"
CSV_FILE="player_stats.csv"
OUT_DIR="../../frontend/public/data/teams"

echo "Downloading FIFA player data..."
curl -L -o "$CSV_FILE" "$CSV_URL"

echo "Importing..."
python import_fifa_data.py --csv "$CSV_FILE" --out "$OUT_DIR"

echo "Done! Files in $OUT_DIR"
ls "$OUT_DIR/club/" | head -10
echo "..."
echo "Total clubs: $(ls $OUT_DIR/club/ | wc -l)"
echo "Total nations: $(ls $OUT_DIR/nation/ | wc -l)"
