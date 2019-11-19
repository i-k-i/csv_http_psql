# csv_http_psql

## How to use 
```bash
git clone https://github.com/i-k-i/csv_http_psql
cd csv_http_psql
docker-compose up -d
docker exec db_filler script.py http://some.csv
```