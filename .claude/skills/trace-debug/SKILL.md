---
name: trace-debug
description: Walk through one pipeline trace (route → queries → retrieved → gate → answer → verifier) and point out where it went wrong.
---
# trace-debug
Args: `<trace_id>` or `last`.

1. `grep -h '"trace_id": "<id>"' logs/traces/*.jsonl | jq -c '{step, model, cached, latency_s}'` for the overview;
   then inspect individual steps with `jq 'select(.step=="...")'`. Never cat whole trace files.
2. Report as a short table: stage · input summary · output summary · latency · verdict (ok / suspicious / wrong).
3. For retrieval stages show top-5 chunk_ids with scores and whether they actually contain the answer
   (`jq` the chunk text from `data/index/chunks.jsonl`).
4. Conclude with the first stage that went wrong and the error-taxonomy label (see `error-analysis`).
