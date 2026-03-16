from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import Counter
import importlib

import streamlit as st

# ====== PROJECT ROOT DETECTION ======
cwd = Path.cwd().resolve()

if (cwd / "src").exists():
    PROJECT_DIR = cwd
elif (cwd.parent / "src").exists():
    PROJECT_DIR = cwd.parent
else:
    raise RuntimeError("Could not find project root containing 'src' folder.")

EVAL_PATH = PROJECT_DIR / "eval" / "eval_results.jsonl"

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# src import / reload
import src.pipeline as pipeline
importlib.reload(pipeline)
from src.pipeline import run_self_correcting

# ====== UI ======
st.set_page_config(page_title="Self-Correcting Validator", layout="wide")
st.title("Self-Correcting Complaint Validator")
st.caption("Interactive demo + evaluation dashboard")

tab1, tab2 = st.tabs(["🧪 Interactive", "📊 Eval Dashboard"])

# ---------- Tab 1: Interactive ----------
with tab1:
    st.subheader("직접 불만 입력 → 구조화 JSON + trace 확인")

    default_text = (
        "배송이 너무 늦어요. 주문번호 2023-9911. "
        "빨리 보내주세요. 연락은 010-1234-1234"
    )
    text = st.text_area("고객 불만 입력", value=default_text, height=160)
    max_attempts = st.slider("max_attempts", 1, 5, 3)

    if st.button("Run", type="primary"):
        try:
            out = run_self_correcting(text, max_attempts=max_attempts)
        except Exception as e:
            st.error(f"Pipeline execution failed: {e}")
            st.stop()

        c1, c2, c3 = st.columns(3)
        c1.metric("OK", str(out.get("ok")))
        c2.metric("Attempts", int(out.get("attempts", 0)))
        c3.metric("Has Final JSON", str(out.get("final") is not None))

        st.markdown("### Final JSON (normalized)")
        if out.get("final") is not None:
            st.code(json.dumps(out["final"], ensure_ascii=False, indent=2), language="json")
        else:
            st.warning("final JSON 없음 (실패)")

        if out.get("errors"):
            st.markdown("### Final Errors")
            st.code(json.dumps(out["errors"], ensure_ascii=False, indent=2), language="json")

        st.markdown("### Trace summary")
        rows = []
        for step in out.get("trace", []):
            rows.append(
                {
                    "attempt": step.get("attempt"),
                    "ok": step.get("ok"),
                    "errors": json.dumps(step.get("errors", []), ensure_ascii=False),
                }
            )
        st.dataframe(rows, use_container_width=True)

        with st.expander("Full trace JSON"):
            st.json(out.get("trace", []))

# ---------- Tab 2: Eval Dashboard ----------
with tab2:
    st.subheader("Eval 결과 요약 (eval_results.jsonl)")

    if not EVAL_PATH.exists():
        st.error(f"파일을 찾을 수 없음: {EVAL_PATH}")
        st.info("먼저 evaluation notebook / script를 실행해서 eval_results.jsonl을 생성해줘.")
        st.stop()

    # Load eval results
    records = []
    with EVAL_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))

    total = len(records)
    ok_recs = [r for r in records if r.get("ok")]
    ok_count = len(ok_recs)
    pass_rate = (ok_count / total) if total else 0.0

    avg_attempts_ok = None
    if ok_count:
        avg_attempts_ok = sum(int(r.get("attempts", 0)) for r in ok_recs) / ok_count

    # Attempt distribution
    attempt_counter = Counter(int(r.get("attempts", 0)) for r in records)

    # Error distribution (final errors)
    error_counter = Counter()
    for r in records:
        for e in (r.get("errors") or []):
            key = f"{e.get('field')}|{e.get('code')}"
            error_counter[key] += 1

    # Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Total", total)
    m2.metric("Pass rate", f"{pass_rate:.2%}")
    m3.metric(
        "Avg attempts (success)",
        f"{avg_attempts_ok:.3f}" if avg_attempts_ok is not None else "N/A"
    )

    st.markdown("### Attempt distribution")
    dist = {str(k): v for k, v in sorted(attempt_counter.items())}
    st.bar_chart(dist)

    st.markdown("### Top error types (field|code)")
    top_k = st.slider("Top K errors", 5, 30, 10)
    top_errors = error_counter.most_common(top_k)
    st.dataframe(
        [{"error": k, "count": v} for k, v in top_errors],
        use_container_width=True,
    )

    st.markdown("### Browse cases")
    show_only_fail = st.checkbox("Show only failures (ok=False)", value=False)
    filtered = [r for r in records if (not show_only_fail or not r.get("ok"))]

    st.write(f"Showing {len(filtered)} / {total} records")

    ids = [r.get("id") for r in filtered]
    selected_id = st.selectbox("Select case id", ids if ids else [None])

    sel = next((r for r in filtered if r.get("id") == selected_id), None)

    if sel:
        st.markdown("#### Input text")
        st.write(sel.get("text", ""))

        st.markdown("#### Result")
        c1, c2 = st.columns(2)
        c1.metric("OK", str(sel.get("ok")))
        c2.metric("Attempts", int(sel.get("attempts", 0)))

        st.markdown("#### Final JSON")
        if sel.get("final") is not None:
            st.code(json.dumps(sel["final"], ensure_ascii=False, indent=2), language="json")
        else:
            st.warning("final JSON 없음 (실패)")

        if sel.get("errors"):
            st.markdown("#### Errors")
            st.code(json.dumps(sel["errors"], ensure_ascii=False, indent=2), language="json")

        with st.expander("Trace (summary JSON)"):
            st.json(sel.get("trace", []))