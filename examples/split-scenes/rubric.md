# Split Scenes Rubric

A good result:

- covers every paragraph exactly once;
- returns contiguous scenes in story order;
- ends the final scene at the final paragraph of the chapter;
- uses scene boundaries for stable place, continuous time, immediate focus, major cast change, or persistent mode shift;
- prefers shorter useful scenes over long mixed scenes;
- keeps summaries short and factual;
- keeps titles concise and specific;
- does not invent events that are not in the chapter.

Validation errors are important evidence. If validation fails, judge whether the prompt or Pydantic model should be adjusted.
