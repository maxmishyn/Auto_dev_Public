from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def read_root() -> dict[str, str]:
    """Basic root endpoint returning a welcome message."""
    return {"message": "Hello, World!"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health check endpoint to verify service availability."""
    return {"status": "ok"}
