from fastapi import FastAPI
from app.db import Base, engine
import app.models  # noqa: F401
from app.routes import accounts, market, debug, admin_market

app = FastAPI(title="Family Investment Site")


@app.on_event("startup")
async def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(accounts.router)
app.include_router(market.router)
app.include_router(debug.router)
app.include_router(admin_market.router)
