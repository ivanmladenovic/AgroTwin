"""Validated AI JSON for parcel intelligence. Invalid payloads never become DB rows."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ParcelIntelligenceAIResult(BaseModel):
    status: Literal["INFO", "WARNING", "CRITICAL", "OK"]
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=4000)
    observed_facts: list[str] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    should_notify: bool = False
    issue_key: str | None = Field(default=None, max_length=128)
    # Optional structured refs (backward compatible — older clients ignore extras in JSON).
    zone_keys: list[str] = Field(default_factory=list)
    tree_public_ids: list[str] = Field(default_factory=list)
    affected_indices: list[str] = Field(default_factory=list)
    observation_date: str | None = Field(default=None, max_length=32)
    data_quality_notes: list[str] = Field(default_factory=list)

    @field_validator("title", "summary")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @field_validator(
        "observed_facts",
        "possible_causes",
        "recommended_actions",
        "data_quality_notes",
    )
    @classmethod
    def clean_lists(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if isinstance(item, str) and item.strip()][:20]

    @field_validator("zone_keys")
    @classmethod
    def clean_zone_keys(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value or []:
            if not isinstance(item, str):
                continue
            key = item.strip()
            if key and key not in cleaned:
                cleaned.append(key[:64])
            if len(cleaned) >= 20:
                break
        return cleaned

    @field_validator("tree_public_ids")
    @classmethod
    def clean_tree_public_ids(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value or []:
            if not isinstance(item, str):
                continue
            key = item.strip().upper()
            if key and key not in cleaned:
                cleaned.append(key[:64])
            if len(cleaned) >= 40:
                break
        return cleaned

    @field_validator("affected_indices")
    @classmethod
    def clean_indices(cls, value: list[str]) -> list[str]:
        allowed = {"ndvi", "ndre", "ndwi"}
        cleaned: list[str] = []
        for item in value or []:
            if not isinstance(item, str):
                continue
            key = item.strip().lower()
            if key in allowed and key not in cleaned:
                cleaned.append(key)
        return cleaned

    @field_validator("observation_date")
    @classmethod
    def clean_observation_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned[:32] or None

    @field_validator("issue_key")
    @classmethod
    def normalize_issue_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower().replace(" ", "_")
        return cleaned[:128] or None
