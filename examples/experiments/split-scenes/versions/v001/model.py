from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationInfo, model_validator


class Scene(BaseModel):
    """One contiguous scene inside a story part."""

    model_config = ConfigDict(extra="forbid")

    identifier: int = Field(description="1-based scene index.")
    summary: str = Field(
        min_length=1,
        description="Short one-sentence summary of what happens in the scene.",
    )
    title: str = Field(..., description="Short scene title")
    paragraph_number: int = Field(
        description="Paragraph number (from chapter text) of the last paragraph of the scene."
    )


class SceneList(RootModel[list[Scene]]):
    """List of scenes."""

    @model_validator(mode="after")
    def validate_scene_division(self, info: ValidationInfo) -> "SceneList":
        """Validate scene-ending paragraph numbers and optional chapter bounds."""
        if not self.root:
            raise ValueError("At least one scene is required.")

        paragraph_numbers = [item.paragraph_number for item in self.root]
        for index, paragraph_number in enumerate(paragraph_numbers[1:], start=1):
            previous_number = paragraph_numbers[index - 1]
            if paragraph_number <= previous_number:
                raise ValueError("Scene paragraph numbers must be strictly increasing.")

        context = info.context if isinstance(info.context, dict) else None
        if context is None:
            return self

        chapter_binding = context.get("chapter")
        if not isinstance(chapter_binding, dict):
            raise ValueError("Scene validation context must include a chapter binding.")
        chapter_data = chapter_binding.get("data")
        if not isinstance(chapter_data, dict):
            raise ValueError("Scene validation context chapter binding must include data.")

        first_part = chapter_data["parts"][0]
        last_part = chapter_data["parts"][-1]
        first_paragraph_number = first_part["first_paragraph_number"]
        last_paragraph_number = last_part["first_paragraph_number"] + len(last_part["paragraphs"]) - 1

        for paragraph_number in paragraph_numbers:
            if paragraph_number < first_paragraph_number or paragraph_number > last_paragraph_number:
                raise ValueError(
                    f"Scene paragraph numbers must stay within chapter range {first_paragraph_number}-{last_paragraph_number}."
                )

        if paragraph_numbers[-1] != last_paragraph_number:
            raise ValueError(
                f"Last scene must end at paragraph {last_paragraph_number}."
            )

        return self
