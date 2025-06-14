from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import router as query_router
from app.core import perform_health_check

app = FastAPI()
app.include_router(query_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return perform_health_check()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)