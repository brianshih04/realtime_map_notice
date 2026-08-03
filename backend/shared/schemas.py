from pydantic import BaseModel, Field
from datetime import datetime


class LocationUpdate(BaseModel):
    user_id: str = Field(..., examples=["u-0001"])
    latitude: float = Field(..., ge=-90, le=90, examples=[25.0173])
    longitude: float = Field(..., ge=-180, le=180, examples=[121.5397])


class EventCreate(BaseModel):
    title: str = Field(..., examples=["Library 3F has seats"])
    message: str = Field(..., examples=["About 10 seats near the windows."])
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    severity: str = Field("info",  examples=["info", "warning", "danger"])
    radius_meters: int = Field(500, ge=50, le=3000)
     # 新增：事件存在時間（分鐘）
    duration_minutes: int = Field(60,ge=1,le=1440,examples=[30, 60, 1440])

    # 新增：圖片 Base64 字串
    image_base64: str | None = Field(None,description="現場照片 Base64 字串")


class EventNotification(BaseModel):
    event_id: str
    title: str
    message: str
    latitude: float
    longitude: float
    severity: str
    distance_meters: float | None = None
    # 新增：通知時保留圖片
    image_base64: str | None = None


class EventResponse(BaseModel):
    event_id: str
    title: str
    message: str
    severity: str
    latitude: float
    longitude: float
    radius_meters: int
    created_at: datetime


class NearbyBroadcast(BaseModel):
    """廣播事件給附近使用者的請求"""
    event_id: str
    title: str
    message: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    severity: str = Field("info", examples=["info", "warning", "danger"])
    radius_meters: int = Field(500, ge=50, le=3000, description="通知範圍（公尺）")
    # 如果廣播也需要帶圖片，可以用
    image_base64: str | None = None
    # 暫定60分鐘，之後可以調整
    duration_minutes: int = Field(60, ge=1, le=1440)

