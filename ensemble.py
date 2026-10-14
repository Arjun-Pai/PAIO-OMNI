# PAIO-Omni · ensemble.py  v3.2
"""
Complexity-scaled answering, per your instruction:

  - simple           -> one model, the normal router.py chain. No change.
  - complicated       -> mixture of experts: 3 different models answer the
                          same question in parallel, then one more call
                          synthesizes them into a single final answer.
  - very_complicated -> parallel tracks of mixture of experts: 2
                          independent MoE groups (3 experts each) run in
                          parallel, each synthesized on its own, then a
                          final meta-synthesis combines both group
                          answers into the ultimate response.

Complexity comes from jev_router.detect_full() — see that module for
the fallback heuristic if Jev is unreachable.

Honest cost/latency note: complicated and very_complicated cost real
time and money — complicated makes 4 model calls total (3 experts + 1
synthesis), very_complicated makes 9 (6 experts + 2 group syntheses + 1
meta-synthesis). This is only worth it for genuinely hard questions,
which is exactly why the fallback heuristic in jev_router.py defaults
to "simple" unless there's a clear signal otherwise.
"""

import concurrent.futures

import cloud_llm
import router

EXPERTS_PER_GROUP = 3
PARALLEL_GROUPS = 2
EXPERT_TIMEOUT = 25.0

# Which roles to pull in as "experts" alongside the primary role Jev
# picked, per group — different angles on the same question rather than
# 3 copies of the same role. Falls back to the primary role repeated if
# a role isn't in this map.
_EXPERT_COMPANIONS = {
    "fast": ["casual", "professional"],
    "brief": ["strict", "fast"],
    "deep": ["scientist", "debate"],
    "casual": ["creative", "teacher"],
    "professional": ["executive", "formal"],
    "formal": ["professional", "strict"],
    "executive": ["professional", "strict"],
    "strict": ["scientist", "formal"],
    "debate": ["deep", "scientist"],
    "scientist": ["deep", "coder"],
    "creative": ["teacher", "casual"],
    "teacher": ["creative", "scientist"],
    "coder": ["scientist", "deep"],
}


def _experts_for(primary_role: str, count: int) -> list:
    companions = _EXPERT_COMPANIONS.get(primary_role, [primary_role, primary_role])
    roles_list = [primary_role] + companions
    while len(roles_list) < count:
        roles_list.append(primary_role)
    return roles_list[:count]


def _ask_one_expert(role_key: str, text: str, history: list, hw_models: dict, vault_path: str) -> str:
    """One expert's answer — reuses the normal provider chain (so it
    still respects your cost-first ordering) but without speaking it out
    loud or touching bubble state; only the final synthesis does that."""
    return router.respond(
        text=text, history=history, mode_key=role_key, hw_models=hw_models,
        vault_path=vault_path, speak_fn=None, state_fn=None,
    )


def _run_expert_group(primary_role: str, text: str, history: list, hw_models: dict, vault_path: str) -> list:
    expert_roles = _experts_for(primary_role, EXPERTS_PER_GROUP)
    answers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=EXPERTS_PER_GROUP) as pool:
        futures = {
            pool.submit(_ask_one_expert, r, text, history, hw_models, vault_path): r
            for r in expert_roles
        }
        for future in concurrent.futures.as_completed(futures, timeout=EXPERT_TIMEOUT + 5):
            role_key = futures[future]
            try:
                answers.append((role_key, future.result(timeout=EXPERT_TIMEOUT)))
            except Exception as e:
                print(f"  [ensemble] expert '{role_key}' failed ({e}) — continuing without it")
    return answers


def _synthesize(text: str, labeled_answers: list, vault_path: str, framing: str) -> str:
    if not labeled_answers:
        return "All the experts I tried for that one failed — can you try rephrasing?"
    if len(labeled_answers) == 1:
        return labeled_answers[0][1]

    blocks = "\n\n".join(f"[{role} perspective]\n{answer}" for role, answer in labeled_answers)
    synthesis_prompt = (
        f"{framing}\n\nOriginal question: {text}\n\n{blocks}\n\n"
        "Combine these into one clear, accurate final answer. Resolve any "
        "disagreements using your own judgment rather than just listing "
        "both sides. Don't mention that this came from multiple sources — "
        "just give the best combined answer."
    )
    try:
        return cloud_llm.chat(
            synthesis_prompt, [], "deep", vault_path,
            provider="zenmux", model=cloud_llm.ZENMUX_MODEL,
        )
    except Exception as e:
        print(f"  [ensemble] synthesis via ZenMux failed ({e}) — using the longest expert answer instead")
        return max((a for _r, a in labeled_answers), key=len)


def answer_complicated(text: str, history: list, primary_role: str, hw_models: dict,
                        vault_path: str, speak_fn=None, state_fn=None) -> str:
    if state_fn:
        state_fn("thinking")
    labeled_answers = _run_expert_group(primary_role, text, history, hw_models, vault_path)
    if state_fn:
        state_fn("making")
    final = _synthesize(text, labeled_answers, vault_path,
                         "Several experts each answered the same question independently.")
    if speak_fn and final:
        speak_fn(final)
    return final


def answer_very_complicated(text: str, history: list, primary_role: str, hw_models: dict,
                             vault_path: str, speak_fn=None, state_fn=None) -> str:
    if state_fn:
        state_fn("thinking")

    group_results = [None] * PARALLEL_GROUPS
    with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL_GROUPS) as pool:
        futures = {
            pool.submit(_run_expert_group, primary_role, text, history, hw_models, vault_path): i
            for i in range(PARALLEL_GROUPS)
        }
        for future in concurrent.futures.as_completed(futures, timeout=EXPERT_TIMEOUT + 10):
            i = futures[future]
            try:
                group_results[i] = future.result()
            except Exception as e:
                print(f"  [ensemble] expert group {i} failed entirely ({e})")
                group_results[i] = []

    if state_fn:
        state_fn("making")

    group_syntheses = []
    for i, labeled_answers in enumerate(group_results):
        synthesis = _synthesize(
            text, labeled_answers, vault_path,
            f"Several experts (group {i + 1} of {PARALLEL_GROUPS}) each answered independently.",
        )
        group_syntheses.append((f"group {i + 1}", synthesis))

    final = _synthesize(
        text, group_syntheses, vault_path,
        "Two independent groups of experts each produced a combined answer, fully in parallel.",
    )
    if speak_fn and final:
        speak_fn(final)
    return final


def answer(text: str, history: list, complexity: str, primary_role: str, hw_models: dict,
           vault_path: str, speak_fn=None, state_fn=None) -> str:
    """Single entry point — dispatches by complexity. "simple" isn't
    handled here; the normal router.respond() call stays the direct
    path for that case, this module is only for the other two."""
    if complexity == "very_complicated":
        return answer_very_complicated(text, history, primary_role, hw_models,
                                        vault_path, speak_fn, state_fn)
    return answer_complicated(text, history, primary_role, hw_models,
                               vault_path, speak_fn, state_fn)
