from fastapi import APIRouter
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter()
project_root = Path(__file__).parent.parent.parent
frontend_dir = project_root / "frontend"

@router.get("/", include_in_schema=False)
async def serve_frontend():
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Frontend not found"}