from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from djamp_service.api import projects, databases, certificates, utilities

app = FastAPI(
    title="DJANGOForge API",
    description="Backend service for DJANGOForge desktop application",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(databases.router, prefix="/api/databases", tags=["databases"])
app.include_router(certificates.router, prefix="/api/certificates", tags=["certificates"])
app.include_router(utilities.router, prefix="/api/utilities", tags=["utilities"])


@app.get("/")
async def root():
    return {"message": "DJANGOForge API", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "djamp_service.main:app", host="127.0.0.1", port=8765, reload=True, log_level="info"
    )
