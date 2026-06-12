"""InsightPilot — Streamlit frontend.

Talks to the FastAPI backend only; contains no data-processing or LLM logic.
Configure the backend via Streamlit secrets (BACKEND_URL) or env var.
"""

from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="InsightPilot — AI Business Analyst",
    page_icon="📊",
    layout="wide",
    menu_items={
        "About": "InsightPilot — privacy-first AI business analytics for e-commerce.",
    },
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 2.2rem; }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.65);
        border: 1px solid #E8E0D0;
        border-radius: 12px;
        padding: 14px 18px;
        box-shadow: 0 1px 3px rgba(43,38,32,0.06);
    }
    div[data-testid="stMetric"] label { color: #8A7E6C; }
    .ip-hero h1 { font-size: 2.4rem; margin-bottom: 0.2rem; }
    .ip-hero p  { color: #6E6354; font-size: 1.05rem; margin-top: 0; }
    .ip-badge {
        display: inline-block; padding: 3px 12px; border-radius: 999px;
        background: #EFE7D8; color: #7A5C3D; font-size: 0.8rem;
        font-weight: 600; letter-spacing: .03em; margin-bottom: .6rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def backend_url() -> str:
    try:
        return st.secrets["BACKEND_URL"].rstrip("/")
    except (KeyError, FileNotFoundError):
        return os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


@st.cache_data(ttl=30, show_spinner=False)
def backend_health(url: str) -> dict | None:
    try:
        r = requests.get(f"{url}/health", timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def fmt_eur(value: float) -> str:
    return f"€{value:,.2f}"


# ─── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 InsightPilot")
    st.caption("AI Business Analyst for E-Commerce")

    url = backend_url()
    health = backend_health(url)
    if health is None:
        st.error(f"Backend unreachable at `{url}`.")
        st.caption(
            "The free-tier backend sleeps after inactivity and needs ~1 minute "
            "to wake up. Try again shortly."
        )
        if st.button("🔄 Retry connection"):
            backend_health.clear()
            st.rerun()
    else:
        st.success(f"Backend connected · v{health['version']}")
        if health["report_enabled"]:
            st.caption("🧠 AI reports: **active**")
        else:
            st.warning("AI reports disabled (no API key on backend). Metrics still work.")

    include_report = st.toggle(
        "Generate AI executive report",
        value=True,
        help="Sends only aggregated KPIs to Claude — never raw rows.",
    )
    st.divider()
    st.markdown(
        "🔒 **Privacy by design**\n\n"
        "Your CSV is processed entirely in memory and never stored. "
        "Only aggregated metrics — never raw transactions or customer data — "
        "are used for the AI report. GDPR-friendly by architecture."
    )
    st.divider()
    st.caption("Works with Shopify order exports and similar CSVs.")

# ─── Hero + Upload ──────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="ip-hero">
      <span class="ip-badge">PRIVACY-FIRST ANALYTICS</span>
      <h1>Your store's numbers, explained.</h1>
      <p>Upload a Shopify-style order CSV → get cleaned KPIs, charts and an
      executive report with concrete next steps. No database, no data retention.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

uploaded = st.file_uploader(
    "Order CSV", type=["csv"], label_visibility="collapsed",
    help="Needs at least: order id, date, total. Product/customer/channel columns unlock more insights.",
)

if uploaded is None:
    st.info(
        "⬆️ Upload a CSV to begin — analysis takes a few seconds. "
        "Need test data? Run `python scripts/generate_synthetic_data.py`."
    )
    st.stop()

if health is None:
    st.stop()

with st.spinner("Cleaning data, computing metrics" + (" and writing your report…" if include_report else "…")):
    try:
        resp = requests.post(
            f"{url}/api/v1/analyze",
            params={"include_report": str(include_report).lower()},
            files={"file": (uploaded.name, uploaded.getvalue(), "text/csv")},
            timeout=300,
        )
    except requests.RequestException as exc:
        st.error(f"Request failed: {exc}")
        st.stop()

if resp.status_code != 200:
    try:
        detail = resp.json().get("detail", resp.text)
    except ValueError:
        detail = resp.text
    st.error(f"Analysis failed ({resp.status_code}): {detail}")
    st.stop()

data = resp.json()
cleaning, metrics, report = data["cleaning"], data["metrics"], data["report"]

# ─── Cleaning summary ───────────────────────────────────────────────────────
with st.expander(
    f"✅ Data quality: {cleaning['rows_after_cleaning']:,} valid rows "
    f"(of {cleaning['rows_received']:,} received)"
):
    c1, c2, c3 = st.columns(3)
    c1.metric("Duplicates removed", cleaning["duplicates_removed"])
    c2.metric("Invalid rows dropped", cleaning["rows_dropped_invalid"])
    c3.metric("Columns recognized", len(cleaning["columns_mapped"]))
    st.caption("Column mapping: " + ", ".join(
        f"`{src}` → `{dst}`" for src, dst in cleaning["columns_mapped"].items()
    ))

# ─── KPIs ───────────────────────────────────────────────────────────────────
st.subheader(f"Key metrics · {metrics['period_start']} → {metrics['period_end']}")

row1 = st.columns(4)
row1[0].metric("Net revenue", fmt_eur(metrics["net_revenue"]))
row1[1].metric("Orders", f"{metrics['total_orders']:,}")
row1[2].metric("Avg. order value", fmt_eur(metrics["average_order_value"]))
growth = metrics["revenue_mom_growth_pct"]
row1[3].metric(
    "Revenue MoM", f"{growth:+.1f}%" if growth is not None else "n/a",
    delta=f"{growth:+.1f}%" if growth is not None else None,
)

row2 = st.columns(4)
row2[0].metric("Customers", f"{metrics['unique_customers']:,}")
row2[1].metric("Repeat rate", f"{metrics['repeat_customer_rate_pct']:.1f}%")
row2[2].metric(
    "Refund rate", f"{metrics['refund_rate_pct']:.1f}%",
    delta=f"{-metrics['refund_rate_pct']:.1f}%" if metrics["refund_rate_pct"] > 5 else None,
    delta_color="inverse",
)
row2[3].metric("Discount share", f"{metrics['discount_share_pct']:.1f}%")

best = metrics.get("best_month")
if best:
    st.caption(f"🏆 Best month: **{best['month']}** with {fmt_eur(best['revenue'])} revenue")

# ─── Tabs: Charts / Breakdown / AI Report ───────────────────────────────────
tab_report, tab_charts, tab_breakdown = st.tabs(
    ["🧠 Executive report", "📈 Trends", "🗂️ Breakdown"]
)

with tab_charts:
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("**Monthly revenue**")
        monthly = pd.DataFrame(metrics["monthly_revenue"])
        if not monthly.empty:
            st.bar_chart(monthly.set_index("month")["revenue"], color="#C2552F")
    with col_right:
        st.markdown("**Top products by revenue**")
        top = pd.DataFrame(metrics["top_products"])
        if not top.empty:
            st.bar_chart(top.set_index("product")["revenue"], horizontal=True, color="#C2552F")

    st.markdown("**Revenue by weekday**")
    st.bar_chart(pd.Series(metrics["revenue_by_weekday"], name="revenue"), color="#8A7E6C")

with tab_breakdown:
    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**Revenue by channel**")
        if metrics["revenue_by_channel"]:
            channel = pd.Series(metrics["revenue_by_channel"], name="Revenue (€)")
            st.dataframe(
                channel.to_frame().style.format("{:,.2f}"),
                use_container_width=True,
            )
    with col4:
        st.markdown("**Revenue by country**")
        if metrics.get("revenue_by_country"):
            country = pd.Series(metrics["revenue_by_country"], name="Revenue (€)")
            st.dataframe(
                country.to_frame().style.format("{:,.2f}"),
                use_container_width=True,
            )
    st.markdown("**Top products**")
    top_tbl = pd.DataFrame(metrics["top_products"])
    if not top_tbl.empty:
        st.dataframe(top_tbl, use_container_width=True, hide_index=True)

with tab_report:
    if report["generated"]:
        st.caption(f"Generated by {report['model']} · grounded in your aggregated KPIs only")
        st.markdown(report["markdown"])
        st.download_button(
            "⬇️ Download report (Markdown)",
            report["markdown"],
            file_name="executive_report.md",
            mime="text/markdown",
        )
    elif include_report and report.get("error"):
        st.warning(f"Report unavailable: {report['error']}")
        st.caption(
            "Backend operators: set `ANTHROPIC_API_KEY` in `backend/.env` "
            "and restart to enable AI reports."
        )
    else:
        st.info("AI report skipped. Enable the toggle in the sidebar and re-upload to generate one.")
