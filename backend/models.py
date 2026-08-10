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


class TaskRespond(BaseModel):
    session_id: str
    response: str
    user_id: str = "local"


class ReminderCreate(BaseModel):
    user_id: str = "local"
    title: str
    description: str = ""
    due_date: str = ""


class ReminderUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: str | None = None
    completed: bool | None = None
