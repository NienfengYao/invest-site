from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = Path("/site/data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "title": "上傳交易 CSV",
            "message": None,
        },
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_csv(
    request: Request,
    account_name: str = Form(...),
    file: UploadFile = File(...),
):
    filename = file.filename or ""

    if not filename.lower().endswith(".csv"):
        return templates.TemplateResponse(
            "upload.html",
            {
                "request": request,
                "title": "上傳交易 CSV",
                "message": "只接受 .csv 檔案",
            },
            status_code=400,
        )

    safe_account = account_name.strip()
    if not safe_account:
        return templates.TemplateResponse(
            "upload.html",
            {
                "request": request,
                "title": "上傳交易 CSV",
                "message": "請輸入帳號",
            },
            status_code=400,
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_name = f"{safe_account}_{timestamp}_{Path(filename).name}"
    save_path = UPLOAD_DIR / save_name

    content = await file.read()
    save_path.write_bytes(content)

    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "title": "上傳交易 CSV",
            "message": f"上傳成功：帳號={safe_account}，檔案={save_name}",
        },
    )
