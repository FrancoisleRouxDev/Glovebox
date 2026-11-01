"""Prompts sent to the vision models.

They live in their own file so they're easy to tweak and to compare in the
eval script without touching the plumbing.
"""

# Shown to the model so it knows the exact shape we will validate against.
_SCHEMA_EXAMPLE = """{
  "is_car": true,
  "candidates": [
    {
      "make": "Toyota",
      "model": "Corolla",
      "generation_or_years": "E210 (2019-present)",
      "body_type": "hatchback",
      "confidence": 0.72
    }
  ],
  "visible_clues": "Toyota badge on grille, narrow LED headlights, hatchback rear."
}"""

SYSTEM_PROMPT = f"""You are an expert car spotter. You identify the make and model of cars in photos.

Respond with a single JSON object and nothing else. It must have exactly this shape:
{_SCHEMA_EXAMPLE}

Rules:
- "is_car": true only if a real car (or light truck/van/SUV) is clearly the main subject.
- "candidates": up to 3 guesses, most likely first. "confidence" is a number from 0 to 1.
  Use null for "generation_or_years" or "body_type" if you can't tell.
- "visible_clues": one or two short sentences on what in the photo led to your guess
  (badges, grille, lights, body shape, text). If there's no car, say what you see instead.
- If there is no car, or the photo is too blurry, dark or cropped to identify it,
  set "is_car" accordingly and return an empty "candidates" list. Do not guess.
- Be honest about uncertainty: lower the confidence instead of inventing details.
"""

USER_PROMPT = "Identify the car in this photo. Reply with the JSON object only."

# Used for the single retry after the model returned invalid JSON.
STRICT_SYSTEM_SUFFIX = """
IMPORTANT: Your previous answer could not be parsed. This time:
- Output ONLY the raw JSON object. No markdown, no code fences, no explanation, no extra keys.
- Use double quotes for all strings and keys. "confidence" must be a number between 0 and 1.
- Problem with the previous answer: {error}
"""


def strict_system_prompt(error: str) -> str:
    """System prompt for the retry, including a short description of what went wrong."""
    # Keep the error short so a huge validation message can't bloat the prompt.
    return SYSTEM_PROMPT + STRICT_SYSTEM_SUFFIX.format(error=error[:300])
