from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.services.market_data import fetch_and_store_monthly_prices 
from app.models.maintenance_log import MaintenanceLog

router = APIRouter(tags=["market"])
templates = Jinja2Templates(directory="app/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/update-market-data")
def update_market_data(db: Session = Depends(get_db)):
    result = fetch_and_store_monthly_prices(db)
    return {
        "status": "ok",
        "result": result,
    }


@router.post("/admin/update-market-data", response_class=HTMLResponse)
def update_market_data_from_page(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        result = fetch_and_store_monthly_prices(db)

        display_result = {
            "總股票數": result.get("total_tickers", 0),
            "成功股票數": result.get("success_tickers", 0),
            "新增月收盤價筆數": result.get("inserted_rows", 0),
            "失敗股票": result.get("failed_tickers", []),
        }

        log = MaintenanceLog(
            task_name="market_price_update",
            success=True,
            message="月收盤價更新完成",
            created_count=result.get("inserted_rows", 0),
            updated_count=result.get("updated_rows", 0),
        )
        db.add(log)
        db.commit()

        return templates.TemplateResponse(
            "maintenance_result.html",
            {
                "request": request,
                "title": "月收盤價更新完成",
                "success": True,
                "result": display_result,
                "message": "月收盤價資料已更新完成。",
            },
        )

    except Exception as exc:
        log = MaintenanceLog(
            task_name="market_price_update",
            success=False,
            message=str(exc),
            created_count=0,
            updated_count=0,
        )
        db.add(log)
        db.commit()

        return templates.TemplateResponse(
            "maintenance_result.html",
            {
                "request": request,
                "title": "月收盤價更新失敗",
                "success": False,
                "result": {},
                "message": str(exc),
            },
            status_code=500,
        )
