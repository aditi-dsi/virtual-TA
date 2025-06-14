from fastapi import FastAPI
from app.api import router as query_router
from app.core import perform_health_check

app = FastAPI()
app.include_router(query_router)

@app.get("/")
def health_check():
    return perform_health_check()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)