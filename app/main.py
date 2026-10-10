from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.router import router
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Bulk Certificate Generator", version="1.0.0", lifespan=lifespan)
app.include_router(router)
