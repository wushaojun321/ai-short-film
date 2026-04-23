from typing import Optional
from pydantic import BaseModel


class PromptConfigUpdate(BaseModel):
    name: Optional[str] = None
    system_prompt: str
    user_prompt_template: str = ""
    description: str = ""
    variables: list[str] = []
    updated_by: str = "admin"
