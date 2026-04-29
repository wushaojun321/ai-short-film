"""STS 临时密钥接口。"""
from fastapi import APIRouter, HTTPException, Depends
from app.services.storage_service import get_sts_credentials
from app.deps import get_current_user

router = APIRouter(tags=["sts"], dependencies=[Depends(get_current_user)])


@router.get("/sts-token")
def get_sts_token():
    """返回 COS STS 临时密钥（有效期 12 小时）。
    
    前端拿到后用 cos-js-sdk-v5 生成预签名 URL 访问私有 bucket 内容。
    """
    try:
        return get_sts_credentials(duration_seconds=43200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STS 申请失败: {e}")
