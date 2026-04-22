from fastapi import FastAPI
from app.db import Base, engine
import app.models  # noqa: F401
from app.routes import accounts, market

app = FastAPI(title="Family Investment Site")


@app.on_event("startup")
async def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(accounts.router)
app.include_router(market.router)
