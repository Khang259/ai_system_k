from typing import Any, Dict, Union

from fastapi.responses import JSONResponse

from application.result import UseCaseResult


def to_http(result: UseCaseResult) -> Dict[str, Any]:
    return result.to_http()


def to_http_or_data(result: UseCaseResult) -> Dict[str, Any]:
    """Endpoints historically returned raw dict (no success wrapper) on success."""
    if not result.success:
        return result.to_http()
    return result.data


def to_http_status(
    result: UseCaseResult, fail_status: int = 503
) -> Union[Dict[str, Any], JSONResponse]:
    """200 khi success; fail_status (mặc định 503) khi chưa sẵn sàng."""
    body = result.to_http()
    if result.success:
        return body
    return JSONResponse(status_code=fail_status, content=body)
