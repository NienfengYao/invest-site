from fastapi import FastAPI
from app.db import Base, engine
import app.models  # noqa: F401
from app.routes.accounts import router as accounts_router

app = FastAPI(title="Family Investment Site")


@app.on_event("startup")
async def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(accounts_router)
