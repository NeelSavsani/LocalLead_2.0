import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as leads_router
from app.config import settings

app = FastAPI(
    title="LocalLeadPulse API",
    description="Automated B2B Lead Generator for Local Businesses without Websites (Two-Layer Verification Pipeline)",
    version="2.0.0",
)

# Enable CORS for Next.js frontend and external API consumers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(leads_router)


@app.get("/")
async def root():
    return {
        "name": "LocalLeadPulse API",
        "version": "2.0.0",
        "status": "online",
        "docs_url": "/docs",
        "pipeline": {
            "layer_1": "Google Maps Listing Website Filter",
            "layer_2": "Organic Search Verification with Aggregator Blacklisting",
            "exporter": "OpenPyXL Styled Workbook with CRM Validation",
        },
    }


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "mock_mode": settings.MOCK_MODE,
        "has_maps_api_key": bool(settings.GOOGLE_MAPS_API_KEY),
        "has_search_api_key": bool(settings.GOOGLE_SEARCH_API_KEY),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
