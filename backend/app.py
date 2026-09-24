"""
app.py
──────
Cab Fare Comparator — Streamlit Dashboard
Uber vs Ola vs Rapido | Live fare comparison for Jaipur routes

Run:  streamlit run app.py
"""

import time
import logging
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()

from utils.location_helper import get_location_names, get_location_query
from utils.data_logger import load_history, clear_history, history_exists
from utils.cookie_manager import cookie_status, delete_cookies, get_cookie_info
from utils.config import HEADLESS, REFRESH_INTERVAL_MINUTES
from utils.logging_config import setup_logging
from utils.analytics import cheapest_win_rate, hourly_average, weekday_average, successful_quotes
from jobs.fetch_fares import fetch_and_log
from scrapers.uber_scraper import UberScraper
from scrapers.ola_scraper import OlaScraper
from scrapers.rapido_scraper import RapidoScraper
from geopy.geocoders import Nominatim

setup_logging()
logger = logging.getLogger(__name__)

# ── Platform config (UI ONLY) ────────────────────────────────────────────────────────────
PLATFORM_CONFIG = {
    "Uber":   {"color": "#000000", "emoji": "⬛", "scraper": UberScraper},
    "Ola":    {"color": "#3CB371", "emoji": "🟢", "scraper": OlaScraper},
    "Rapido": {"color": "#FFD700", "emoji": "🟡", "scraper": RapidoScraper},
}

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cab Fare Comparator",
    page_icon="🚖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

  /* ── Base ────────────────────────────────────────── */
  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
  }

  h1, h2, h3 {
    font-family: 'Syne', sans-serif !important;
    font-weight: 800 !important;
  }

  .main { background: #0d0d0d; }
  .block-container { padding: 2rem 2rem 4rem; }

  /* ── Hero header ─────────────────────────────────── */
  .hero-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border-radius: 16px;
    padding: 2.5rem 3rem;
    margin-bottom: 2rem;
    border: 1px solid rgba(255,255,255,0.08);
    position: relative;
    overflow: hidden;
  }
  .hero-header::before {
    content: "🚖";
    position: absolute;
    right: 2rem;
    top: 50%;
    transform: translateY(-50%);
    font-size: 6rem;
    opacity: 0.12;
  }
  .hero-title {
    font-family: 'Syne', sans-serif;
    font-size: 2.4rem;
    font-weight: 800;
    color: #ffffff;
    margin: 0;
    line-height: 1.1;
  }
  .hero-title span { color: #f5a623; }
  .hero-sub {
    color: rgba(255,255,255,0.55);
    font-size: 0.95rem;
    margin-top: 0.5rem;
    font-weight: 300;
  }

  /* ── Fare cards ──────────────────────────────────── */
  .fare-card {
    background: #161616;
    border-radius: 16px;
    padding: 1.5rem;
    border: 1px solid rgba(255,255,255,0.07);
    transition: transform 0.2s, border-color 0.2s;
    height: 100%;
  }
  .fare-card:hover {
    transform: translateY(-3px);
    border-color: rgba(255,255,255,0.15);
  }
  .fare-card.cheapest {
    border: 2px solid #22c55e;
    background: linear-gradient(135deg, #0d1f0d, #0a1a0a);
    box-shadow: 0 0 30px rgba(34, 197, 94, 0.15);
  }
  .fare-card.error {
    border-color: rgba(239, 68, 68, 0.3);
    background: #1a0d0d;
  }

  .platform-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'Syne', sans-serif;
    font-size: 0.85rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 4px 12px;
    border-radius: 20px;
    margin-bottom: 1rem;
  }
  .cheapest-badge {
    background: #22c55e;
    color: #000;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-left: 8px;
  }
  .fare-amount {
    font-family: 'Syne', sans-serif;
    font-size: 2.2rem;
    font-weight: 800;
    color: #ffffff;
    line-height: 1;
    margin: 0.5rem 0;
  }
  .ride-type {
    color: rgba(255,255,255,0.45);
    font-size: 0.8rem;
    font-weight: 400;
    margin-top: 0.2rem;
  }
  .eta-text {
    color: rgba(255,255,255,0.6);
    font-size: 0.85rem;
    margin-top: 0.8rem;
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .error-msg {
    color: #ef4444;
    font-size: 0.8rem;
    margin-top: 0.5rem;
    word-break: break-word;
  }
  .savings-pill {
    background: rgba(34,197,94,0.12);
    color: #22c55e;
    border: 1px solid rgba(34,197,94,0.25);
    border-radius: 8px;
    padding: 0.5rem 1rem;
    font-size: 0.85rem;
    font-weight: 500;
    text-align: center;
    margin-top: 1rem;
  }

  /* ── Status bar ──────────────────────────────────── */
  .status-bar {
    background: #111;
    border-radius: 10px;
    padding: 0.75rem 1.25rem;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.82rem;
    color: rgba(255,255,255,0.5);
    border: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 1.5rem;
  }
  .status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #22c55e;
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  /* ── Section headers ─────────────────────────────── */
  .section-header {
    font-family: 'Syne', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: rgba(255,255,255,0.85);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }

  /* ── Sidebar ─────────────────────────────────────── */
  [data-testid="stSidebar"] {
    background: #0d0d0d !important;
    border-right: 1px solid rgba(255,255,255,0.06);
  }
  [data-testid="stSidebar"] label {
    font-family: 'DM Sans', sans-serif !important;
    color: rgba(255,255,255,0.7) !important;
  }

  /* ── Buttons ─────────────────────────────────────── */
  .stButton > button {
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
    border: none !important;
    transition: all 0.2s !important;
  }
  .stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3) !important;
  }

  /* ── Cookie status ───────────────────────────────── */
  .cookie-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.6rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
  }
  .cookie-platform { font-weight: 600; font-size: 0.9rem; }
  .cookie-ok   { color: #22c55e; }
  .cookie-miss { color: #ef4444; }

  /* ── Info box ────────────────────────────────────── */
  .info-box {
    background: rgba(59,130,246,0.08);
    border: 1px solid rgba(59,130,246,0.2);
    border-radius: 10px;
    padding: 0.8rem 1.2rem;
    font-size: 0.82rem;
    color: rgba(255,255,255,0.65);
    line-height: 1.6;
  }
  .info-box strong { color: #60a5fa; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  Helper functions
# ══════════════════════════════════════════════════════════════════════════════

def fetch_all_fares(pickup: str, destination: str, selected: list) -> list:
    """Demo mode — mock fares, still logged with mode='demo'."""
    return fetch_and_log(pickup, destination, selected, mode="demo")


def fetch_real_fares(pickup: str, destination: str, selected: list) -> list:
    """Live scrapes, one platform at a time, with retries. Logged to SQLite."""
    return fetch_and_log(
        pickup,
        destination,
        selected,
        mode="real",
        headless=st.session_state.get("headless", HEADLESS),
    )


def find_cheapest(results: list) -> str | None:
    """Return platform name of cheapest successful result."""
    successful = [r for r in results if r["status"] == "success" and r["fare_min"] > 0]
    if not successful:
        return None
    return min(successful, key=lambda r: r["fare_min"])["platform"]


def render_fare_card(result: dict, is_cheapest: bool, savings: int = 0):
    """Render a single platform's fare card as HTML."""
    platform = result["platform"]
    cfg = PLATFORM_CONFIG.get(platform, {"color": "#888", "emoji": "🚗"})

    cheapest_cls = "cheapest" if is_cheapest else ""
    error_cls    = "error"    if result["status"] == "error" else ""
    card_cls     = f"fare-card {cheapest_cls} {error_cls}".strip()

    cheapest_badge = '<span class="cheapest-badge">✓ CHEAPEST</span>' if is_cheapest else ""

    if result["status"] == "success":
        content = f"""
<div class="fare-amount">{result['fare']}</div>
<div class="ride-type">{result['ride_type']}</div>
<div class="eta-text">🕐 ETA: {result['eta']}</div>
{f'<div class="savings-pill">💰 Save ₹{savings} vs most expensive</div>' if is_cheapest and savings > 0 else ''}
{f'<div class="ride-type" style="margin-top:6px;font-size:0.72rem;opacity:0.5">{result.get("error_msg", "")}</div>' if result.get("error_msg") else ''}
"""
    else:
        content = f"""
<div class="fare-amount" style="font-size:1.4rem;color:#666">Unavailable</div>
<div class="error-msg">⚠ {result['error_msg']}</div>
"""

    return f"""
<div class="{card_cls}">
  <div>
    <span class="platform-badge" style="background:{cfg['color']}22;color:{cfg['color']};border:1px solid {cfg['color']}44">
      {cfg['emoji']} {platform}
    </span>
    {cheapest_badge}
  </div>
{content}
</div>
"""


def build_bar_chart(results: list, cheapest_platform: str):
    """Build a Plotly horizontal bar chart of fares."""
    data = [r for r in results if r["status"] == "success" and r["fare_min"] > 0]
    if not data:
        return None

    platforms = [r["platform"] for r in data]
    fares     = [r["fare_min"] for r in data]
    colors    = [
        "#22c55e" if r["platform"] == cheapest_platform else PLATFORM_CONFIG.get(r["platform"], {}).get("color", "#555")
        for r in data
    ]

    fig = go.Figure(go.Bar(
        x=fares,
        y=platforms,
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"₹{f}" for f in fares],
        textposition="outside",
        textfont=dict(color="white", size=13, family="Syne"),
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="rgba(255,255,255,0.7)", family="DM Sans"),
        xaxis=dict(
            showgrid=True, gridcolor="rgba(255,255,255,0.06)",
            zeroline=False, showticklabels=True,
            title=dict(text="Fare (₹)", font=dict(size=11, color="rgba(255,255,255,0.4)")),
        ),
        yaxis=dict(showgrid=False),
        margin=dict(l=10, r=60, t=10, b=30),
        height=200,
        bargap=0.35,
    )
    return fig


def build_history_chart(df: pd.DataFrame, pickup: str, destination: str):
    """Build a Plotly line chart of fare history for the current route."""
    route_df = df[
        (df["pickup"] == pickup)
        & (df["destination"] == destination)
        & (df["status"] == "success")
    ]

    if route_df.empty:
        return None

    fig = px.line(
        route_df, x="timestamp", y="fare_min", color="platform",
        color_discrete_map={
            "Uber": "#ffffff", "Ola": "#3CB371", "Rapido": "#FFD700"
        },
        markers=True,
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="rgba(255,255,255,0.7)", family="DM Sans"),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False,
                   title=dict(text="Fare (₹)")),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=10, r=10, t=10, b=30),
        height=300,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  Session state init
# ══════════════════════════════════════════════════════════════════════════════

def init_session():
    defaults = {
        "fare_results":    [],
        "last_fetch_time": None,
        "auto_refresh":    False,
        "refresh_interval": REFRESH_INTERVAL_MINUTES,
        "headless":        HEADLESS,
        "pickup_custom":   "",
        "dest_custom":     "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


# ══════════════════════════════════════════════════════════════════════════════
#  Sidebar
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown('<p class="section-header">⚙️ Settings</p>', unsafe_allow_html=True)

    # Profile Mode (Demo vs Real)
    st.markdown("**Profile Mode**")
    profile_mode = st.radio("Choose Mode", [
        "1. Demo Mode (No Login - Mock Data)", 
        "2. Real Scraper (Requires Login)"
    ], key="profile_mode")
    st.divider()

    # Platform selection
    st.markdown("**Platforms**")
    sel_uber   = st.checkbox("Uber",   value=True)
    sel_ola    = st.checkbox("Ola",    value=True)
    sel_rapido = st.checkbox("Rapido", value=True)
    selected_platforms = [p for p, v in [("Uber", sel_uber), ("Ola", sel_ola), ("Rapido", sel_rapido)] if v]

    st.divider()

    # Auto-refresh
    st.markdown("**Auto-Refresh**")
    auto_refresh = st.toggle("Enable Auto-Refresh", value=st.session_state.auto_refresh)
    st.session_state.auto_refresh = auto_refresh

    if auto_refresh:
        interval = st.slider("Interval (minutes)", 1, 30, st.session_state.refresh_interval)
        st.session_state.refresh_interval = interval
        st.caption(f"🔄 Fares refresh every **{interval} min**")

    st.divider()

    # Browser mode
    st.markdown("**Browser Mode**")
    headless = st.toggle("Headless (no browser window)", value=st.session_state.headless)
    st.session_state.headless = headless

    st.divider()

    # Cookie status panel
    st.markdown("**🍪 Cookie Status**")
    cookie_info = cookie_status()
    for platform, has_cookies in cookie_info.items():
        icon = "✅" if has_cookies else "❌"
        info = get_cookie_info(platform)
        count_str = f"({info['count']} cookies)" if has_cookies else "(no session)"
        st.markdown(
            f"{icon} **{platform.capitalize()}** <span style='color:rgba(255,255,255,0.35);font-size:0.75rem'>{count_str}</span>",
            unsafe_allow_html=True
        )
        if has_cookies:
            if st.button(f"Delete {platform.capitalize()} cookies", key=f"del_{platform}", use_container_width=True):
                delete_cookies(platform)
                st.rerun()

    st.divider()
    st.markdown(
        '<div class="info-box"><strong>Tip:</strong> First run → set <code>HEADLESS=False</code> in .env so you can see the browser and handle OTP login. After saving cookies, enable headless mode.</div>',
        unsafe_allow_html=True
    )


# Login Guard removed to allow direct access to UI
# ══════════════════════════════════════════════════════════════════════════════
#  Main tabs
# ══════════════════════════════════════════════════════════════════════════════

tab_compare, tab_history, tab_analytics, tab_login, tab_about = st.tabs([
    "🚖 Compare Fares", "📈 Fare History", "📊 Analytics", "🔐 Login Manager", "ℹ️ About"
])


# ────────────────────────────────────────────────────────────
#  TAB 1 — Compare Fares
# ────────────────────────────────────────────────────────────
with tab_compare:

    # Hero
    st.markdown("""
    <div class="hero-header">
      <p class="hero-title">Cab Fare <span>Comparator</span></p>
      <p class="hero-sub">Real-time fares · Uber vs Ola vs Rapido · Jaipur routes</p>
    </div>
    """, unsafe_allow_html=True)

    # Route selection
    st.markdown('<p class="section-header">📍 Select Route</p>', unsafe_allow_html=True)

    location_names = get_location_names()

    col_p, col_d = st.columns(2)

    with col_p:
        pickup_mode = st.radio("Pickup", ["📍 Preset location", "✏️ Type custom"], horizontal=True, key="pickup_mode")
        if pickup_mode == "📍 Preset location":
            pickup_sel = st.selectbox("Pickup location", location_names, index=3, key="pickup_sel")
            from utils.location_helper import get_location_query
            pickup_query = get_location_query(pickup_sel)
        else:
            pickup_query = st.text_input("Type pickup address", placeholder="e.g. Hawa Mahal, Jaipur", key="pickup_custom_input")

    with col_d:
        dest_mode = st.radio("Destination", ["📍 Preset location", "✏️ Type custom"], horizontal=True, key="dest_mode")
        if dest_mode == "📍 Preset location":
            dest_sel = st.selectbox("Destination location", location_names, index=1, key="dest_sel")
            dest_query = get_location_query(dest_sel)
        else:
            dest_query = st.text_input("Type destination address", placeholder="e.g. Jaipur Airport", key="dest_custom_input")

    # Route summary
    if pickup_query and dest_query:
        st.markdown(f"""
        <div class="status-bar">
          <span>🗺️</span>
          <span style="color:rgba(255,255,255,0.7)">{pickup_query}</span>
          <span style="color:#f5a623">→</span>
          <span style="color:rgba(255,255,255,0.7)">{dest_query}</span>
        </div>
        """, unsafe_allow_html=True)

        with st.spinner("Loading map..."):
            try:
                geolocator = Nominatim(user_agent="cab_comparator")
                # Add 'Jaipur' if not in string to improve geocoding
                p_q = pickup_query if "Jaipur" in pickup_query else f"{pickup_query}, Jaipur"
                d_q = dest_query if "Jaipur" in dest_query else f"{dest_query}, Jaipur"
                
                p_loc = geolocator.geocode(p_q, timeout=3)
                d_loc = geolocator.geocode(d_q, timeout=3)
                
                coords = []
                if p_loc:
                    coords.append({"lat": p_loc.latitude, "lon": p_loc.longitude})
                if d_loc:
                    coords.append({"lat": d_loc.latitude, "lon": d_loc.longitude})
                
                if coords:
                    df_map = pd.DataFrame(coords)
                    st.map(df_map, zoom=11, use_container_width=True)
            except Exception as e:
                logger.error(f"Geocoding error: {e}")

    # Fetch button
    col_btn, col_time = st.columns([2, 3])
    with col_btn:
        fetch_clicked = st.button(
            "🔍 Fetch Fares Now",
            type="primary",
            use_container_width=True,
            disabled=not (pickup_query and dest_query and selected_platforms),
        )

    with col_time:
        if st.session_state.last_fetch_time:
            st.caption(f"Last fetched: {st.session_state.last_fetch_time.strftime('%H:%M:%S')}")

    # Trigger fetch
    should_fetch = fetch_clicked

    # Auto-refresh logic
    if st.session_state.auto_refresh and st.session_state.last_fetch_time:
        elapsed = (datetime.now() - st.session_state.last_fetch_time).total_seconds() / 60
        if elapsed >= st.session_state.refresh_interval:
            should_fetch = True
            st.toast(f"🔄 Auto-refreshing fares...", icon="🔄")

    if should_fetch and pickup_query and dest_query and selected_platforms:
        with st.spinner(f"🚗 Fetching fares from {', '.join(selected_platforms)}..."):
            if "Demo Mode" in st.session_state.profile_mode:
                results = fetch_all_fares(pickup_query, dest_query, selected_platforms)
            else:
                results = fetch_real_fares(pickup_query, dest_query, selected_platforms)

        st.session_state.fare_results = results
        st.session_state.last_fetch_time = datetime.now()

    # ── Results display ────────────────────────────────────────────────────────
    results = st.session_state.fare_results

    if results:
        cheapest = find_cheapest(results)
        successful = [r for r in results if r["status"] == "success" and r["fare_min"] > 0]

        # Savings calculation
        savings = 0
        if cheapest and len(successful) > 1:
            max_fare = max(r["fare_min"] for r in successful)
            cheapest_fare = next(r["fare_min"] for r in successful if r["platform"] == cheapest)
            savings = max_fare - cheapest_fare

        # Summary banner
        if cheapest:
            cfg = PLATFORM_CONFIG.get(cheapest, {})
            st.success(
                f"{cfg.get('emoji','✅')} **{cheapest}** is cheapest right now!"
                + (f" You save ₹{savings} vs most expensive option." if savings > 0 else "")
            )

        st.markdown('<p class="section-header">💰 Current Fares</p>', unsafe_allow_html=True)

        # Fare cards in columns
        cols = st.columns(len(results))
        for i, result in enumerate(results):
            is_cheapest = result["platform"] == cheapest
            with cols[i]:
                st.markdown(
                    render_fare_card(result, is_cheapest, savings if is_cheapest else 0),
                    unsafe_allow_html=True
                )

        # Bar chart
        if successful:
            st.markdown('<p class="section-header" style="margin-top:2rem">📊 Visual Comparison</p>', unsafe_allow_html=True)
            chart = build_bar_chart(results, cheapest)
            if chart:
                st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": False})

        # Raw data toggle
        with st.expander("🔍 Raw data (for debugging)"):
            st.json(results)

    elif not fetch_clicked:
        st.markdown("""
        <div style="text-align:center; padding: 4rem 2rem; color: rgba(255,255,255,0.2)">
          <div style="font-size:4rem">🚖</div>
          <p style="font-size:1.1rem; margin-top:1rem; font-family:Syne,sans-serif">Select a route and click "Fetch Fares"</p>
          <p style="font-size:0.85rem">Supports Uber, Ola & Rapido across Jaipur</p>
        </div>
        """, unsafe_allow_html=True)

    # Auto-refresh: rerun only when the interval has elapsed (no 1-second busy loop)
    if st.session_state.auto_refresh and st.session_state.last_fetch_time:
        elapsed_s = (datetime.now() - st.session_state.last_fetch_time).total_seconds()
        remaining = max(0, st.session_state.refresh_interval * 60 - elapsed_s)
        st.caption(f"⏱ Next auto-refresh in {int(remaining) // 60}m {int(remaining) % 60}s")
        if remaining > 0:
            time.sleep(min(15, remaining))
            st.rerun()


# ────────────────────────────────────────────────────────────
#  TAB 2 — Fare History
# ────────────────────────────────────────────────────────────
with tab_history:
    st.markdown('<p class="section-header">📈 Fare History</p>', unsafe_allow_html=True)

    if not history_exists():
        st.info("No fare history yet. Fetch some fares first!")
    else:
        df = load_history()
        if df.empty:
            st.info("No fare history yet. Fetch some fares first!")
        else:
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            min_d = df["timestamp"].min().date() if pd.notna(df["timestamp"].min()) else datetime.now().date()
            max_d = df["timestamp"].max().date() if pd.notna(df["timestamp"].max()) else datetime.now().date()
            with col_f1:
                start_d = st.date_input("From", value=min_d, min_value=min_d, max_value=max_d, key="hist_from")
            with col_f2:
                end_d = st.date_input("To", value=max_d, min_value=min_d, max_value=max_d, key="hist_to")
            with col_f3:
                mode_opts = ["all"] + sorted(df["mode"].dropna().unique().tolist()) if "mode" in df.columns else ["all"]
                mode_f = st.selectbox("Mode", mode_opts)
            with col_f4:
                plat_opts = sorted(df["platform"].dropna().unique().tolist())
                plats_f = st.multiselect("Platforms", plat_opts, default=plat_opts)

            filtered = df.copy()
            ts = pd.to_datetime(filtered["timestamp"], utc=True, errors="coerce")
            filtered = filtered[(ts.dt.date >= start_d) & (ts.dt.date <= end_d)]
            if mode_f != "all" and "mode" in filtered.columns:
                filtered = filtered[filtered["mode"] == mode_f]
            if plats_f:
                filtered = filtered[filtered["platform"].isin(plats_f)]

            col_stats1, col_stats2, col_stats3 = st.columns(3)
            with col_stats1:
                n_runs = filtered["scrape_run_id"].nunique() if "scrape_run_id" in filtered.columns else len(filtered)
                st.metric("Scrape runs", n_runs)
            with col_stats2:
                ok = filtered[(filtered["status"] == "success") & (filtered["fare_min"] > 0)]
                st.metric("Avg fare", f"₹{ok['fare_min'].mean():.0f}" if not ok.empty else "—")
            with col_stats3:
                st.metric("Failed quotes", int((filtered["status"] != "success").sum()))

            routes = filtered.groupby(["pickup", "destination"]).size().reset_index()
            routes["route"] = routes["pickup"].str[:25] + " → " + routes["destination"].str[:25]

            if len(routes) > 0:
                selected_route = st.selectbox("Filter by route", ["All routes"] + routes["route"].tolist())
                if selected_route != "All routes":
                    idx = routes[routes["route"] == selected_route].index[0]
                    pickup_f = routes.loc[idx, "pickup"]
                    dest_f = routes.loc[idx, "destination"]
                    chart = build_history_chart(filtered, pickup_f, dest_f)
                    if chart:
                        st.plotly_chart(chart, use_container_width=True)
                    filtered = filtered[
                        (filtered["pickup"] == pickup_f) & (filtered["destination"] == dest_f)
                    ]

            st.markdown("**Recorded quotes (including failures):**")
            cols = [c for c in [
                "timestamp", "platform", "ride_type", "fare", "eta", "status",
                "error_msg", "mode", "pickup", "destination",
            ] if c in filtered.columns]
            display_df = filtered[cols].sort_values("timestamp", ascending=False)
            st.dataframe(display_df, use_container_width=True, height=350)
            st.download_button(
                "Download CSV",
                display_df.to_csv(index=False).encode("utf-8"),
                file_name="fare_history_export.csv",
                mime="text/csv",
            )

            if st.button("🗑️ Clear History", type="secondary"):
                clear_history()
                st.success("History cleared!")
                st.rerun()


# ────────────────────────────────────────────────────────────
#  TAB 3 — Analytics
# ────────────────────────────────────────────────────────────
with tab_analytics:
    st.markdown('<p class="section-header">📊 Trend Analysis</p>', unsafe_allow_html=True)

    if not history_exists():
        st.info("Need some stored fares before trends can be computed.")
    else:
        df = load_history()
        ok = successful_quotes(df)
        if ok.empty:
            st.warning("No successful quotes yet — demo mode or a real scrape will populate this.")
        else:
            st.caption("Times shown in Asia/Kolkata. Failed scrapes are excluded from averages.")

            wins = cheapest_win_rate(df)
            if not wins.empty:
                st.markdown("**Who is cheapest most often?**")
                wcols = st.columns(len(wins))
                for i, (_, row) in enumerate(wins.iterrows()):
                    with wcols[i]:
                        st.metric(
                            row["platform"],
                            f"{row['win_rate']}%",
                            help=f"{int(row['wins'])} of {int(row['runs'])} runs",
                        )

            hourly = hourly_average(df)
            if not hourly.empty:
                st.markdown("**Average fare by hour of day**")
                fig_h = px.line(
                    hourly, x="hour", y="fare_min", color="platform",
                    markers=True,
                    color_discrete_map={"Uber": "#ffffff", "Ola": "#3CB371", "Rapido": "#FFD700"},
                )
                fig_h.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="rgba(255,255,255,0.7)"),
                    xaxis=dict(title="Hour (IST)", dtick=1, showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
                    yaxis=dict(title="Avg fare (₹)", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
                    legend=dict(bgcolor="rgba(0,0,0,0)"),
                    height=320, margin=dict(l=10, r=10, t=10, b=30),
                )
                st.plotly_chart(fig_h, use_container_width=True, config={"displayModeBar": False})

            weekly = weekday_average(df)
            if not weekly.empty:
                st.markdown("**Average fare by day of week**")
                fig_w = px.bar(
                    weekly, x="weekday", y="fare_min", color="platform", barmode="group",
                    color_discrete_map={"Uber": "#ffffff", "Ola": "#3CB371", "Rapido": "#FFD700"},
                )
                fig_w.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="rgba(255,255,255,0.7)"),
                    xaxis=dict(title=""),
                    yaxis=dict(title="Avg fare (₹)", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
                    legend=dict(bgcolor="rgba(0,0,0,0)"),
                    height=320, margin=dict(l=10, r=10, t=10, b=30),
                )
                st.plotly_chart(fig_w, use_container_width=True, config={"displayModeBar": False})

            spread = (
                ok.groupby("scrape_run_id")["fare_min"]
                .agg(cheapest="min", priciest="max")
                .reset_index()
            )
            spread["savings"] = spread["priciest"] - spread["cheapest"]
            if not spread.empty:
                st.metric("Avg savings vs most expensive option", f"₹{spread['savings'].mean():.0f}")


# ────────────────────────────────────────────────────────────
#  TAB 4 — Login Manager
# ────────────────────────────────────────────────────────────
with tab_login:
    st.markdown('<p class="section-header">🔐 Login Manager</p>', unsafe_allow_html=True)

    st.markdown("""
    <div class="info-box" style="margin-bottom:1.5rem">
      <strong>How it works:</strong><br>
      Click a platform button below → a Chrome window opens → log in manually
      (enter phone + OTP) → cookies are saved automatically → future runs don't
      need manual login.
    </div>
    """, unsafe_allow_html=True)

    cookie_info = cookie_status()

    for platform in ["Uber", "Ola", "Rapido"]:
        has_cookies = cookie_info.get(platform.lower(), False)
        info        = get_cookie_info(platform.lower())
        cfg         = PLATFORM_CONFIG[platform]

        with st.expander(
            f"{cfg['emoji']} {platform}  —  {'✅ Session saved' if has_cookies else '❌ Not logged in'}",
            expanded=not has_cookies
        ):
            col_a, col_b = st.columns(2)

            with col_a:
                if st.button(f"🌐 Open {platform} & Login", key=f"login_{platform}", use_container_width=True, type="primary"):
                    st.info(f"Opening {platform} in Chrome... Log in manually, then wait for cookies to be saved.")
                    scraper = PLATFORM_CONFIG[platform]["scraper"](headless=False)
                    scraper.start_driver()
                    logged_in = scraper.login()
                    scraper.quit_driver()
                    if logged_in:
                        st.success(f"✅ {platform} cookies saved!")
                    else:
                        st.error(f"❌ {platform} login failed or timed out.")
                    st.rerun()

            with col_b:
                if has_cookies:
                    if st.button(f"🗑️ Delete {platform} cookies", key=f"del2_{platform}", use_container_width=True):
                        delete_cookies(platform.lower())
                        st.warning(f"{platform} cookies deleted.")
                        st.rerun()

            if has_cookies:
                st.markdown(f"""
                <div style='color:rgba(255,255,255,0.45);font-size:0.78rem;margin-top:0.5rem'>
                  {info['count']} cookies saved · {info['size_kb']} KB
                </div>
                """, unsafe_allow_html=True)

    st.divider()
    st.markdown("**Or use environment variables:**")
    st.code("""
# .env file
UBER_PHONE=+919876543210
UBER_PASSWORD=your_password

OLA_PHONE=+919876543210
OLA_PASSWORD=your_ola_password

RAPIDO_PHONE=+919876543210
RAPIDO_PASSWORD=your_rapido_password
    """, language="bash")


# ────────────────────────────────────────────────────────────
#  TAB 4 — About
# ────────────────────────────────────────────────────────────
with tab_about:
    st.markdown("""
    ## 🚖 Cab Fare Comparator

    **B.Tech Semester Project** — Automated real-time fare comparison across Uber, Ola & Rapido.

    ---

    ### Tech Stack

    | Tool | Role |
    |---|---|
    | **Python 3.10+** | Core language |
    | **Selenium 4** | Browser automation |
    | **BeautifulSoup4** | HTML parsing |
    | **Streamlit** | Dashboard UI |
    | **SQLite** | Fare history + scrape runs |
    | **APScheduler** | Background collection |
    | **webdriver-manager** | Auto ChromeDriver |
    | **Plotly** | Charts |
    | **python-dotenv** | Env var management |
    | **pandas** | Data handling |

    ---

    ### Architecture

    ```
    app.py (Streamlit UI — reads history, optional live fetch)
      │
      ├── jobs/fetch_fares.py   ← shared scrape + retry + log
      ├── scheduler.py          ← APScheduler interval job
      ├── scrapers/             ← Uber / Ola / Rapido Selenium
      └── utils/
            ├── storage.py      ← SQLite (routes, runs, quotes)
            ├── analytics.py    ← hour / weekday / win-rate
            └── logging_config  ← logs/app.log
    ```

    ---

    ### ⚠️ Disclaimer

    This tool is for **educational purposes only**. Web scraping may violate the
    Terms of Service of Uber, Ola, and Rapido. Use on your own accounts only.
    Do not deploy publicly.

    ---

    **Built by Deepak** · B.Tech CSE · 3rd Year Semester Project
    """)
