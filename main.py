
import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))
from fastapi import FastAPI
from app.route import router
from fastapi.middleware.cors import CORSMiddleware

# Force default event loop policy to avoid uvloop issues
import asyncio
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())



middleware = [
    {
        "middleware_class": CORSMiddleware,
        "allow_origins": ["*"],
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
]
app = FastAPI(title="Superbill Generator")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])   
app.include_router(router)


def main():
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True, loop="asyncio")
    
    
if __name__ == "__main__":
    main()