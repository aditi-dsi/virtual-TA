import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.schemas import QueryRequest
from app.core import handle_query

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/query")
async def query_processor(request: QueryRequest):
    try:
        response = await handle_query(request)
        return response
    except Exception as e:
        logger.error(f"Error in processing query: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})