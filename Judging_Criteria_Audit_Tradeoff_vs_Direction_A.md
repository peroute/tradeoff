---
Judging Criteria Audit — Tradeoff vs. Direction A

---
How the criteria map to your codebase

From CLAUDE.md:

| Criterion | Weight | Owned By |
| --- | --- | --- |
| AI reasoning | 30% | Stage 3 what-if insights + Stage 2b grounding |
| Solution design | 25% | Pipeline architecture, scope enforcement, hard/soft split |
| Impact & insight | 15% | Dashboard — does the output change behavior? |
| Responsible AI | 10% | validate_output(), HumanBoundaryBanner, source verification |

---
Score-by-score breakdown

AI Reasoning (30%) — Strong, one gap

What you have that scores well:

The 7-slot structured reasoning is genuinely not a list generator. Each insight is required to name a specific fact key, quote the user's exact
words, pass a 6-rule deterministic gate, and produce a verb-led next action. The slot composition (2 base + 2 contingency + 2 priority_match + 1
synthesis) shows structured thinking about what kind of reasoning to surface, not just how much.

The source verification (verified/claimed/unapproved → confidence degradation) is sophisticated. Showing 1 withheld visibly in the panel is a
stronger signal than hiding failures.

The gap that costs points:

The brief says "help users explore what happens if… questions." Your scenario types (lottery_risk, extension_risk, employer_switch) answer these
questions but the UI never frames them as questions. An insight card labelled "Lottery risk" and containing a paragraph about odds is not
obviously the same as "What if you don't win the H-1B lottery three years in a row?" — which is what judges are looking for. The question is
implicit; judges should not have to infer it.

The raw key problem: The insight card shows fact · bundle_a.visa_enrichment.lottery_cumulative_3yr in monospace. To you this proves grounding. To
a judge who glances for 90 seconds it reads as unfinished debugging output.

---
Solution Design (25%) — Very strong

What you have:
- The citizenship-specific visa routing is the genuine differentiator. Other teams will have GPT generate "consider the H-1B" without modeling the
user's actual citizenship or the lottery math.
- SupportedCountry as a Literal type enforced at the API boundary (CompareRequest) before any pipeline stage runs is clean architecture. The fact
that a 7th country cannot reach the LLM is architectural, not just documented.
- ThreadPoolExecutor parallel fact assembly.
- The hard/soft split is architecturally enforced, not a convention. visa_rules.json facts genuinely cannot come from an LLM call.
- The _flatten_keys() single-source-of-truth pattern for the fact bundle is sophisticated.

The small risk: Solution design is partly judged through the pitch. If you can't explain in 60 seconds why citizenship matters to immigration
routing, the implementation depth is invisible.

---
Impact & Insight (15%) — The weakest area

This criterion asks: how does this change what the user does next?

What you have:
Every insight has a next_action field. The synthesis insight is the highest-order output. The sacrifice map radar shows where each path wins.

What's missing:

There is no culminating decision moment. The dashboard presents 7 independent insight cards, a radar chart, a wage panel, an outlook panel, and a
caveats panel. After seeing all of this, what does the user do? They are expected to synthesize across all sections themselves.

The next_action fields across the 7 insights together form an action plan — but they are buried inside individual cards at the bottom of a long
scroll. A judge looking for "how insights change user behavior" might scroll past all of it without seeing a single coherent "here's what to do
next."

The sacrifice map winner ("a" / "b" / "tie") is computed per dimension but never aggregated: "Country A leads on 2 of 5 dimensions" is information
that currently exists in the data but is not shown anywhere.

---
Responsible AI (10%) — Excellent, probably the best this criterion can score

This is your narrative anchor for the pitch. You have not one safeguard but four, layered:

1. validate_output() — deterministic, dependency-free, 6 rules, routes failures to SafeFallback not to silence
2. SafeFallback shown visibly — "1 withheld" + WithheldCard with reason, not hidden
3. HumanBoundaryBanner — sticky, contrasting background, "You make the call"
4. Source verification — three-verdict system with confidence degradation, no URL substitution

The brief says "at least one responsible AI safeguard." You have a system of them with architectural enforcement. This is likely the strongest
implementation of this criterion across competing teams.

---
Common mistakes checklist — how you fare

| Judge complaint | Status | Evidence |
| --- | --- | --- |
| AI generates lists without reasoning through tradeoffs | Avoided | Each insight names a specific fact, quotes the user, and must pass 6 deterministic checks |
| Presenting outputs as 'correct answers' | Avoided | HumanBoundaryBanner, "We never pick for you", SafeFallback for failures |
| No clear user decision moment | Partially failing | next_action fields exist but are scattered; there is no synthesis into a concrete "here is what to do" |
| 'Machine learning analyzes patterns' vagueness | Avoided | Every insight traces to a dotted fact key and a grounding source |

---
What to fix before the deadline

These are ordered by scoring impact. All are frontend-only or copy changes — no backend work needed.

1. Frame insights as "what if" questions (AI reasoning +)

Add a question header above each insight card based on scenario_type. The answers already exist in consideration and next_action. The questions do
not.

SCENARIO_QUESTION: Record<ScenarioType, string> = {
  base: 'What does working here actually look like for you?',
  lottery_risk: 'What if you don't win the H-1B lottery?',
  extension_risk: 'What if your visa renewal is denied?',
  employer_switch: 'What if you need to change jobs mid-visa?',
  partner_work: 'What can your partner do in each country?',
  pr_timeline: 'What if PR takes longer than expected?',
  priority_match: 'How does each country match what you said matters?',
  synthesis: 'Where does the sharpest tradeoff actually sit?',
}

Render it as a small italic line above consideration in InsightCard. This is a 10-line change that directly quotes the brief's language back at
judges.

2. Surface the raw fact keys as human-readable labels (AI reasoning +)

The fact · bundle_a.visa_enrichment.lottery_cumulative_3yr chip looks like a debugging artifact. Replace the raw dotted key with a short human
label in the card. Two options:

Option A (low effort): After fact · split on . and join the last 2 segments: lottery_cumulative_3yr → lottery · 3yr cumulative. Simple string
transform, no data changes.

Option B (right answer): Add a fact_label to the WhatIfInsight model and have Stage 3 populate it. Too much for today.

Option A takes 5 minutes and is good enough for a demo.

3. Add "Your next moves" panel (impact +)

Extract all next_action fields from passing insights and render them as a numbered checklist below the insights section. Every field is already in
the payload.

const nextActions = insights
  .filter((i): i is WhatIfInsight => i.type === 'insight')
  .map((i) => i.next_action)

// Render as <ol> with numbered items

This creates the explicit "user decision moment" that the brief and the marking rubric both require. A user can leave the page with a concrete
list of 6 actions. This is a 20-line component.

4. Move the synthesis insight to the top of the panel (impact +)

Currently insights render in slot order: base, base, contingency, contingency, priority_match, priority_match, synthesis. The synthesis slot
contains the highest-order cross-country tradeoff — it's the most valuable insight and it's last.

Sort by: synthesis first, then priority_match, then contingency, then base. Or just add a visual "synthesized view" callout above the list that
shows only the synthesis card. One sort call in InsightsPanel.

5. Add a dimension score count to the sacrifice map header (impact +)

"Country A leads on 2 of 5 dimensions"

This is computable from model.comparison.filter(c => c.winner === 'a').length. It is not picking a winner — it is reporting the numerical balance
of evidence. This is the closest thing to a decision-relevant summary currently missing from the dashboard.

6. Stronger HumanBoundaryBanner copy (responsible AI tone)

Current: "This tool lays out the trade-offs from cited data — it never recommends which country to choose."

This sounds apologetic. The brief wants a decision moment, not an absence of one.

Consider: "The evidence is in. What you do with it is yours." — same constraint, frames it as empowerment rather than limitation. Small copy
change, no code change.

---
How to pitch this

The 90-second version:

▎ "Most teams will ask GPT to compare two countries. We built a system where an Indian computer science grad vs. a Nigerian finance grad gets a
▎ completely different routing — because their citizenship actually determines which visa they can apply for, what the lottery odds are, and
▎ whether their partner can work. The AI's job is to surface what the numbers mean for this specific person's situation, not to generate a generic
▎ comparison. Every insight is checked against the actual data before it appears on screen — if it can't cite a real fact and quote something you
▎ said, it's shown as withheld, not hidden."

Three things judges will ask, and your answers:

"How is this different from just asking ChatGPT?" — ChatGPT cannot tell an Indian citizen that their H-1B 3-year lottery success probability is
36%, that their partner can only work on an H-4 EAD, and that Germany's Blue Card path to PR is 2 years shorter — all from live OECD wages,
curated visa rules, and Google-grounded policy research, tied to what that specific user said they care about.

"How do you prevent the AI from hallucinating?" — We don't prevent it; we detect and discard it. Every insight passes 6 deterministic checks
before it renders. If it fails any check, a SafeFallback card appears with the exact reason. The AI never states a visa salary floor or lottery
odds — those come from curated JSON with cited government URLs and a last_verified date.

"What does the user actually decide after using this?" — (Currently: unclear. After fix #3 above: "Here are your 6 next moves.")

---
Summary verdict

| Dimension | Current | Potential (with fixes) |
| --- | --- | --- |
| AI reasoning (30%) | Good — structured, grounded, gated | Very good — add "what if" question framing |
| Solution design (25%) | Very good — citizenship-specific routing is real | Same — already strong |
| Impact & insight (15%) | Moderate — insights exist but no action plan | Good — 20-line "next moves" panel |
| Responsible AI (10%) | Excellent — best possible story | Same — fix banner copy only |
| Common mistakes | 3/4 avoided | 4/4 with decision moment fix |

The code is strong. The gap is entirely in how the output is framed and surfaced. Fixes 1–4 above are all frontend changes totalling under 100
lines, and they directly address the one weakness judges are most likely to flag: "I see data, but what does this person do next?"
