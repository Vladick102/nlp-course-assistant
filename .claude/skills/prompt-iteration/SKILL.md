---
name: prompt-iteration
description: Change one prompt in prompts/, bump its version, run the component eval on dev, and keep or revert based on the metric.
---
# prompt-iteration
Args: `<prompt_name> "<hypothesis>"`.

1. Read the latest error analysis for the component that uses the prompt; state the hypothesis (which error bucket it fixes).
2. Copy current prompt to `prompts/archive/<name>_v<old>.md`, edit, bump `version:`.
3. Run `run-eval` for the owning component on **dev**.
4. Keep if headline metric improves and no guard metric regresses; otherwise restore the archived version (and its version
   number). Either way log the row in `reports/eval/history.md` with "kept? yes/no".
