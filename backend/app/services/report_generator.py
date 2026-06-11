"""Executive report generation via the Claude API.

Receives only aggregated metrics (see data_processing.metrics.to_llm_payload).
Uses streaming with get_final_message() so long reports don't hit HTTP timeouts.

Note on model parameters: the default model (claude-fable-5) supports adaptive
thinking only and rejects sampling parameters (temperature/top_p/top_k), so we
send neither. Keep it that way unless you switch to an older model family.
"""

from __future__ import annotations

import json

import anthropic

from app.config import Settings
from app.models.schemas import Metrics, ReportResult

SYSTEM_PROMPT = """\
You are a senior e-commerce business analyst writing for a busy store owner with
no data background. You receive pre-computed, aggregated store metrics as JSON
(no raw transactions). Write an executive report in Markdown with exactly these
sections:

# Executive Summary
3-4 sentences: overall health of the business, the single most important number,
and the single biggest opportunity or risk.

## Key Performance Indicators
A compact Markdown table of the most decision-relevant KPIs with a one-line
interpretation each. Use the currency symbol € unless the data suggests otherwise.

## What's Working
2-4 bullet points grounded in the data (cite the numbers).

## What Needs Attention
2-4 bullet points on risks or underperformance (cite the numbers).

## Recommended Actions
3-5 numbered, concrete, prioritized actions a small e-commerce team can execute
in the next 30 days. Each action must reference the metric that motivates it and
state the expected effect.

Rules:
- Ground every claim in the provided numbers; never invent data.
- If a metric is missing or zero, say so rather than speculating.
- Plain language, no jargon without a one-phrase explanation.
- Keep the whole report under ~700 words.
"""


def generate_report(metrics: Metrics, settings: Settings) -> ReportResult:
    if not settings.report_enabled:
        return ReportResult(
            generated=False,
            error="Report generation is not configured (ANTHROPIC_API_KEY is not set). "
                  "Metrics were computed successfully.",
        )

    payload = json.dumps(metrics.model_dump(), ensure_ascii=False)
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        with client.messages.stream(
            model=settings.report_model,
            max_tokens=settings.report_max_tokens,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    "Here are the aggregated store metrics as JSON. "
                    "Write the executive report.\n\n" + payload
                ),
            }],
        ) as stream:
            message = stream.get_final_message()
    except anthropic.AuthenticationError:
        return ReportResult(generated=False, error="Invalid Anthropic API key.")
    except anthropic.RateLimitError:
        return ReportResult(generated=False, error="Claude API rate limit reached — try again shortly.")
    except anthropic.APIStatusError as exc:
        return ReportResult(generated=False, error=f"Claude API error ({exc.status_code}): {exc.message}")
    except anthropic.APIConnectionError:
        return ReportResult(generated=False, error="Could not reach the Claude API (network error).")

    if message.stop_reason == "refusal":
        return ReportResult(generated=False, model=message.model,
                            error="The model declined to generate this report.")

    text = "".join(block.text for block in message.content if block.type == "text")
    if message.stop_reason == "max_tokens":
        text += "\n\n*Report truncated at the configured token limit.*"

    return ReportResult(generated=True, model=message.model, markdown=text)
