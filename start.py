import uvicorn
from core.fast_api import get_fast_api_app

if __name__ == "__main__":
    app = get_fast_api_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)