from pydantic import BaseModel, Field, model_validator


class ExpenseCreate(BaseModel):
    group_id: str
    paid_by: str
    amount: int = Field(gt=0, le=9_223_372_036_854_775_807)
    category: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=500)
    method: str
    participants: list[str]
    values: list[int] | None = None

    @model_validator(mode="after")
    def validate_lengths(self):
        if self.values is not None and len(self.values) != len(self.participants):
            raise ValueError("values must match participants")
        return self


class SettlementCreate(BaseModel):
    group_id: str
    sender_id: str
    receiver_id: str
    amount: int = Field(gt=0, le=9_223_372_036_854_775_807)
