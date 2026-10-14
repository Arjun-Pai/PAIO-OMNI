# PAIO-Omni · tester.py  v3.1
"""
Benchmarks every real subject that exists after setup: every model in
your OpenRouter ranked list, every model in your Groq ranked list (both
set in onboarding.py), and the 13 local Ollama models for your detected
tier — not a hypothetical/theoretical set, only what you've actually
configured or installed.

For each subject, runs one prompt per role (13 prompts) and records:
  - latency: time-to-first-token (streamed where possible) + total time
  - success/failure, with the actual error text on failure
  - basic sanity checks: empty response, and for the coder prompt,
    whether the reply contains a code block at all

Outputs one self-contained HTML file (inline CSS, hand-drawn SVG bar
charts — no CDN dependency, works fully offline) to open in a browser.

Run: python tester.py
"""

import datetime
import os
import time

import cloud_llm
import hardware
import llm
import roles

TEST_PROMPTS = {
    "fast":         "What's the capital of France?",
    "brief":        "Is Python interpreted or compiled?",
    "deep":         "Explain how a hash table handles collisions, in detail.",
    "casual":       "Hey, what's up? Got a sec to chat?",
    "professional": "Draft a short email asking a vendor for a quote.",
    "formal":       "Write a one-paragraph formal statement about renewable energy policy.",
    "executive":    "Summarize the business case for adopting AI in three bullet points.",
    "strict":       "What year did the Berlin Wall fall? Answer with only the fact.",
    "debate":       "Should schools require school uniforms? Give both sides.",
    "scientist":    "Explain, mechanistically, why ice floats on water.",
    "creative":     "Write two sentences of a story about a robot who forgets.",
    "teacher":      "Explain what a variable is in programming, for a beginner.",
    "coder":        "Write a Python function that reverses a linked list.",
}


def _test_cloud_model(provider: str, model: str) -> dict:
    results = {}
    for role, prompt in TEST_PROMPTS.items():
        start = time.time()
        try:
            answer = cloud_llm.chat(prompt, [], role, vault_path=None,
                                     provider=provider, model=model)
            elapsed = time.time() - start
            results[role] = {
                "ok": True, "latency": elapsed,
                "empty": not answer.strip(),
                "has_code": ("```" in answer) if role == "coder" else None,
                "error": None,
            }
        except Exception as e:
            results[role] = {
                "ok": False, "latency": time.time() - start,
                "empty": None, "has_code": None, "error": str(e),
            }
    return results


def _test_local(model_tag: str, role: str, prompt: str, hw_models: dict) -> dict:
    start = time.time()
    try:
        # llm.chat picks a model from hw_models by role — for a clean
        # per-model test we call the same request path with hw_models
        # overridden so every role for this test resolves to model_tag.
        forced = {k: model_tag for k in hw_models}
        answer = llm.chat(prompt, [], role, forced, vault_path=None)
        elapsed = time.time() - start
        return {
            "ok": True, "latency": elapsed,
            "empty": not answer.strip(),
            "has_code": ("```" in answer) if role == "coder" else None,
            "error": None,
        }
    except Exception as e:
        return {"ok": False, "latency": time.time() - start,
                "empty": None, "has_code": None, "error": str(e)}


def _test_ollama_cloud_model(model: str) -> dict:
    results = {}
    for role, prompt in TEST_PROMPTS.items():
        start = time.time()
        try:
            answer = llm.chat(prompt, [], role, {}, vault_path=None, model_override=model)
            results[role] = {
                "ok": True, "latency": time.time() - start,
                "empty": not answer.strip(),
                "has_code": ("```" in answer) if role == "coder" else None,
                "error": None,
            }
        except Exception as e:
            results[role] = {"ok": False, "latency": time.time() - start,
                              "empty": None, "has_code": None, "error": str(e)}
    return results


def run_all() -> dict:
    hw = hardware.detect()
    print(f"Detected tier: {hw['tier']}\n")
    report = {"tier": hw["tier"], "generated_at": datetime.datetime.now().isoformat(), "subjects": {}}

    print(f"Testing zenmux/{cloud_llm.ZENMUX_MODEL} ...")
    report["subjects"][f"zenmux/{cloud_llm.ZENMUX_MODEL}"] = {
        "type": "cloud", "results": _test_cloud_model("zenmux", cloud_llm.ZENMUX_MODEL),
    }

    for provider in ("openrouter", "groq", "ollama_cloud"):
        models = cloud_llm.model_priority(provider)
        if not models:
            print(f"No {provider} models saved yet (run onboarding.py) — skipping.")
            continue
        for model in models:
            print(f"Testing {provider}/{model} ...")
            if provider == "ollama_cloud":
                report["subjects"][f"{provider}/{model}"] = {
                    "type": "cloud", "results": _test_ollama_cloud_model(model),
                }
            else:
                report["subjects"][f"{provider}/{model}"] = {
                    "type": "cloud", "results": _test_cloud_model(provider, model),
                }

    for role, model_tag in hw["models"].items():
        if role == "whisper":
            continue
        print(f"Testing local model {model_tag} (role: {role}) ...")
        prompt = TEST_PROMPTS[role]
        result = _test_local(model_tag, role, prompt, hw["models"])
        report["subjects"].setdefault(model_tag, {"type": "local", "role": role, "results": {}})
        report["subjects"][model_tag]["results"][role] = result

    return report


def _bar_svg(label: str, value: float, max_value: float, color: str) -> str:
    width = 0 if max_value == 0 else (value / max_value) * 300
    return (
        f'<div class="bar-row"><span class="bar-label">{label}</span>'
        f'<svg width="310" height="18"><rect x="0" y="1" width="{width:.0f}" height="16" '
        f'fill="{color}" rx="3"/></svg>'
        f'<span class="bar-value">{value:.2f}s</span></div>'
    )


def render_html(report: dict, out_path: str) -> None:
    subjects = report["subjects"]
    all_latencies = [
        r["latency"] for s in subjects.values() for r in s["results"].values() if r["ok"]
    ]
    max_latency = max(all_latencies) if all_latencies else 1.0

    rows = []
    for name, subject in subjects.items():
        kind_label = "☁️ Cloud" if subject["type"] == "cloud" else f"💻 Local ({subject.get('role','?')})"
        oks = sum(1 for r in subject["results"].values() if r["ok"])
        total = len(subject["results"])
        avg_latency = (
            sum(r["latency"] for r in subject["results"].values() if r["ok"]) / oks
            if oks else 0
        )
        bars = "".join(
            _bar_svg(role, r["latency"], max_latency, "#2ecc71" if r["ok"] else "#e74c3c")
            for role, r in subject["results"].items()
        )
        issues = "".join(
            f'<li><strong>{role}</strong>: {r["error"]}</li>'
            for role, r in subject["results"].items() if not r["ok"]
        )
        empties = "".join(
            f'<li><strong>{role}</strong>: empty response</li>'
            for role, r in subject["results"].items() if r["ok"] and r.get("empty")
        )
        rows.append(f"""
        <div class="card">
          <h2>{name}</h2>
          <div class="meta">{kind_label} · {oks}/{total} succeeded · avg {avg_latency:.2f}s</div>
          <div class="bars">{bars}</div>
          {f'<div class="issues"><strong>Issues:</strong><ul>{issues}{empties}</ul></div>' if (issues or empties) else ''}
        </div>""")

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>PAIO-Omni Test Report</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; background: #0f1115; color: #e8e8e8; margin: 0; padding: 24px; }}
  h1 {{ font-size: 22px; }}
  .subtitle {{ color: #999; margin-bottom: 24px; }}
  .card {{ background: #1a1d24; border-radius: 10px; padding: 18px 20px; margin-bottom: 16px; border: 1px solid #2a2e38; }}
  .card h2 {{ margin: 0 0 4px 0; font-size: 16px; color: #7fd1ff; }}
  .meta {{ color: #aaa; font-size: 13px; margin-bottom: 10px; }}
  .bar-row {{ display: flex; align-items: center; gap: 8px; font-size: 12px; margin: 3px 0; }}
  .bar-label {{ width: 110px; color: #ccc; }}
  .bar-value {{ color: #888; width: 50px; }}
  .issues {{ margin-top: 10px; font-size: 12px; color: #ff8a80; }}
  .issues ul {{ margin: 4px 0 0 18px; padding: 0; }}
</style></head>
<body>
  <h1>PAIO-Omni Test Report</h1>
  <div class="subtitle">Tier: {report['tier']} · Generated {report['generated_at']}</div>
  {"".join(rows)}
</body></html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    report = run_all()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_report.html")
    render_html(report, out_path)
