from enum import Enum


class AgentTypeEnum(str, Enum):
    GOOGLE_ADK = "GOOGLE_ADK"
    LANGCHAIN = "LANGCHAIN"
    LITELLM = "LITELLM"
    OPENAI_SDK = "OPENAI_SDK"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"

    def __str__(self) -> str:
        return str(self.value)
