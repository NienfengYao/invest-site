!Docker
* Path: /volume1/docker/invest-site
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
* 進入container 裡面，執行python 互動模式
  * sudo docker exec -it invest-site python



* curl -X POST http://127.0.0.1:8000/update-market-data
* curl -X POST http://<NAS_IP>:8000/update-market-data
