from pydantic import BaseModel


class TextQuery(BaseModel):
    text: str
    user_id: str = "local"
    tier: str = "free"


class DocumentUpload(BaseModel):
    user_id: str
    file_name: str
    file_type: str
    content_b64: str


class LicenseActivate(BaseModel):
    key: str


class LiveKitTokenRequest(BaseModel):
    identity: str = "second-brain-user"
    room_name: str = "second-brain"
