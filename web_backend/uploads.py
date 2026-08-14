"""Shared guards for web-upload endpoints."""

from fastapi import HTTPException, UploadFile

from .config import settings


async def read_upload_bytes(upload: UploadFile) -> bytes:
    """Read one upload while enforcing the configured request-file ceiling.

    FastAPI's ``UploadFile`` is spooled, but ``await read()`` still materialises
    the whole file in memory. Read at most limit+1 so oversized input is rejected
    before application code creates an unbounded bytes object.
    """
    limit = settings.max_upload_size
    content = await upload.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"上传文件不能超过 {limit // (1024 * 1024)} MB",
        )
    return content
