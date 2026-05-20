!Docker
* Path: cd /volume1/docker/invest-site
* 列出目前正在運行的 container
  * sudo docker ps [-a]
* 重建 container (修改 code 後進行測試)
  * sudo docker-compose down (停掉並刪除所有compose 啟動的container)
  * sudo docker-compose build --no-cache
  * sudo docker-compose up -d
  * sudo docker logs invest-site (看 log 確認啟動正常)
* 開發模式, 會 reload *.py/*.html
  * sudo docker-compose up
    * 改 *.py -> 存檔 -> 自動 reload
    * 改 template -> 刷新瀏覽器 -> 立即看到
  * ssh 斷線後，終端 session 消失，重新接回 log
    * sudo docker logs -f invest-site
* 進入container 裡面，互動模式
  * sudo docker exec -it invest-site python
  * sudo docker exec -it invest-site bash
* 目前需要手動更新月收盤價
  * curl -X POST http://127.0.0.1:8000/update-market-data
  * http://NAS-IP:8000/debug/
    * rebuild-monthly-holdings/1
    * rebuild-monthly-performance/1
/debug/rebuild-monthly-performance/1
* Debug
  * debug/db
