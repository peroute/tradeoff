"""Locked stage chain for the post-grad decision comparator.

Stage order (do not collapse or reorder — see CLAUDE.md):
    1.  intake            (deterministic)
    2a. fact_assembly     (deterministic)
    2b. outlook_step      (AI call #1 — Gemini + Google Search grounding)
    3.  reasoning_step    (AI call #2 — Gemini what-if)
    4.  reasoning_step.validate_output  (deterministic gate -> SAFE_FALLBACK)
    5.  sacrifice_diff    (deterministic cross-option diff)
    6.  dashboard         (output)
"""
