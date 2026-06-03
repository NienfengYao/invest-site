# Docker

## 建立乾淨測試環境
```
$ cd /volume1/docker/invest-site
$ sudo docker-compose down
$ sudo rm -f data/invest.db
$ sudo docker-compose build --no-cache
$ sudo docker-compose up -d
$ sudo docker logs -f invest-site

# Optional
$ sudo docker ps [-a] # 列出目前正在運行的 container
$ sudo docker-compose up # 開發模式, 會 reload .py/.html

# 進入container 裡面，互動模式
$ sudo docker exec -it invest-site python
$ sudo docker exec -it invest-site bash
```
* 確認網站可開：http://NAS-IP:8000/


## 操作流程
* 在首頁建立帳戶
* 點選帳戶，匯入交易資料(.csv)
  * /debug/db?account_id=Account_ID
* 目前需要手動更新月收盤價
  * curl -X POST http://127.0.0.1:8000/update-market-data
* 重建 monthly_holdings
  * /debug/rebuild-monthly-holdings/Account_ID
  * /debug/db?account_id=Account_ID
* 更新股息資訊
  * /debug/update-dividends
* 重建 monthly_performance
  * /debug/rebuild-monthly-performance/Account_ID
