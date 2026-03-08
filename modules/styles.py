import streamlit as st


MAIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

/* ========== CORE RESETS & VARIABLES ========== */
:root {
    --primary-500: #3B82F6;
    --primary-400: #60A5FA;
    --primary-600: #2563EB;
    --accent-500: #8B5CF6;
    --accent-400: #A78BFA;
    --dark-900: #0A0E1A;
    --dark-800: #0F172A;
    --dark-700: #1E293B;
    --dark-600: #334155;
    --light-100: #F1F5F9;
    --light-200: #E2E8F0;
    --light-300: #CBD5E1;
    --light-400: #94A3B8;
    --font-display: 'Rajdhani', sans-serif;
    --font-body: 'IBM Plex Sans', sans-serif;
    --transition-swift: 200ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-smooth: 350ms cubic-bezier(0.4, 0, 0.2, 1);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: var(--font-body);
    background: linear-gradient(135deg, var(--dark-900) 0%, var(--dark-800) 50%, #0D1525 100%);
    color: var(--light-200);
    overflow-x: hidden;
}

.main .block-container { padding: 1rem 1.5rem; max-width: 100% !important; }

/* ========== HEADER ========== */
.clio-header {
    background: linear-gradient(135deg, rgba(59,130,246,0.08) 0%, rgba(139,92,246,0.06) 100%);
    border-bottom: 1px solid rgba(59,130,246,0.15);
    padding: 1rem 1.5rem;
    margin: -1rem -1.5rem 1.5rem -1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
}
.clio-logo { display: flex; align-items: baseline; gap: 0.5rem; }
.clio-logo-text {
    font-family: var(--font-display);
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    background: linear-gradient(135deg, var(--primary-400) 0%, var(--accent-400) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.clio-tagline {
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 400;
    color: var(--light-400);
    letter-spacing: 0.15em;
    text-transform: uppercase;
}
.clio-status { display: flex; align-items: center; gap: 0.5rem; font-size: 0.75rem; color: var(--light-300); }
.status-indicator {
    width: 6px; height: 6px; border-radius: 50%;
    background: linear-gradient(135deg, #10B981 0%, #34D399 100%);
    box-shadow: 0 0 8px rgba(16,185,129,0.6);
    animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.7; transform: scale(1.1); }
}

/* ========== COLUMNS ========== */
.clio-column {
    background: rgba(30,41,59,0.35);
    border: 1px solid rgba(59,130,246,0.12);
    border-radius: 0.5rem;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    display: flex; flex-direction: column;
    overflow: hidden;
    transition: border-color var(--transition-swift);
}
.clio-column:hover { border-color: rgba(59,130,246,0.25); }
.column-header {
    padding: 1rem 1.25rem;
    border-bottom: 1px solid rgba(59,130,246,0.1);
    background: linear-gradient(135deg, rgba(59,130,246,0.05) 0%, rgba(139,92,246,0.03) 100%);
}
.column-title {
    font-family: var(--font-display);
    font-size: 0.875rem; font-weight: 600;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--primary-400); margin: 0;
}
.column-subtitle { font-family: var(--font-body); font-size: 0.7rem; color: var(--light-400); margin-top: 0.25rem; font-weight: 300; }
.column-content { flex: 1; overflow-y: auto; overflow-x: hidden; padding: 1rem; }
.column-content::-webkit-scrollbar { width: 4px; }
.column-content::-webkit-scrollbar-track { background: rgba(15,23,42,0.3); }
.column-content::-webkit-scrollbar-thumb { background: rgba(59,130,246,0.3); border-radius: 2px; }
.column-content::-webkit-scrollbar-thumb:hover { background: rgba(59,130,246,0.5); }

/* ========== CHAT MESSAGES ========== */
.message-group { margin-bottom: 1.5rem; animation: messageSlideIn var(--transition-smooth) ease-out; }
@keyframes messageSlideIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
.message-user { display: flex; justify-content: flex-end; margin-bottom: 0.75rem; }
.message-assistant { display: flex; justify-content: flex-start; margin-bottom: 0.75rem; }
.message-bubble {
    max-width: 85%; padding: 0.875rem 1.125rem; border-radius: 0.75rem;
    font-size: 0.875rem; line-height: 1.5; font-family: var(--font-body);
    transition: transform var(--transition-swift);
}
.message-bubble:hover { transform: translateY(-1px); }
.message-bubble-user {
    background: linear-gradient(135deg, var(--primary-600) 0%, var(--primary-500) 100%);
    color: white; border-bottom-right-radius: 0.25rem;
    box-shadow: 0 4px 12px rgba(59,130,246,0.2);
}
.message-bubble-assistant {
    background: rgba(30,41,59,0.6); color: var(--light-200);
    border: 1px solid rgba(59,130,246,0.15); border-bottom-left-radius: 0.25rem;
}

/* ========== VIZ & REPORT PLACEHOLDERS ========== */
.viz-placeholder {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    height: 300px; color: var(--light-400); text-align: center; padding: 2rem;
}
.viz-placeholder-icon { font-size: 3rem; margin-bottom: 1rem; opacity: 0.3; }
.viz-placeholder-text { font-family: var(--font-body); font-size: 0.875rem; font-weight: 300; }

.report-item {
    background: rgba(15,23,42,0.3); border: 1px solid rgba(59,130,246,0.08);
    border-radius: 0.375rem; padding: 0.875rem; margin-bottom: 0.75rem;
    transition: all var(--transition-swift);
}
.report-item:hover { background: rgba(15,23,42,0.5); border-color: rgba(59,130,246,0.15); }
.report-item-header {
    font-family: var(--font-display); font-size: 0.75rem; font-weight: 600;
    color: var(--primary-400); margin-bottom: 0.5rem;
    text-transform: uppercase; letter-spacing: 0.05em;
}
.report-item-content { font-family: var(--font-body); font-size: 0.8rem; color: var(--light-300); line-height: 1.4; }

/* ========== STREAMLIT OVERRIDES ========== */
.stChatMessage { background: transparent !important; padding: 0 !important; }
.stChatInput { background: rgba(30,41,59,0.6) !important; border: 1px solid rgba(59,130,246,0.2) !important; border-radius: 0.5rem !important; }
.stChatInput input { font-family: var(--font-body) !important; color: var(--light-200) !important; }
.stDataFrame { background: transparent !important; }
.js-plotly-plot { background: transparent !important; }
.streamlit-expanderHeader {
    background: rgba(30,41,59,0.4) !important;
    border: 1px solid rgba(59,130,246,0.15) !important;
    border-radius: 0.375rem !important;
    font-family: var(--font-body) !important;
    font-size: 0.8rem !important;
    color: var(--light-300) !important;
}
.streamlit-expanderContent {
    background: rgba(15,23,42,0.3) !important;
    border: 1px solid rgba(59,130,246,0.1) !important;
    border-top: none !important;
}

/* ========== MODE SELECTOR ========== */
.mode-selector-container {
    background: linear-gradient(135deg, rgba(59,130,246,0.1) 0%, rgba(139,92,246,0.1) 100%);
    border: 1px solid rgba(59,130,246,0.2);
    border-radius: 12px; padding: 1rem; margin: 1rem 0; text-align: center;
}
.mode-selector-title {
    font-size: 0.9rem; font-weight: 600; color: #94A3B8;
    margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em;
}

/* ========== PDF MODE ========== */
.pdf-col {
    background: rgba(15,23,42,0.6); border: 1px solid rgba(59,130,246,0.15);
    border-radius: 10px; overflow: hidden; height: 100%;
}
.pdf-col-hdr {
    padding: 0.65rem 1rem; border-bottom: 1px solid rgba(59,130,246,0.12);
    background: linear-gradient(135deg,rgba(59,130,246,0.08),rgba(139,92,246,0.05));
    font-family: 'Rajdhani',sans-serif; font-size: 0.82rem; font-weight: 700;
    letter-spacing: .1em; text-transform: uppercase; color: #60A5FA;
}
.pdf-col-body { padding: 0.75rem; }
.chat-bubble-user {
    background: linear-gradient(135deg,rgba(59,130,246,0.25),rgba(139,92,246,0.2));
    border: 1px solid rgba(59,130,246,0.3); border-radius: 12px 12px 4px 12px;
    padding: 0.65rem 0.9rem; margin-bottom: 0.4rem; font-size: 0.85rem; color: #E2E8F0;
}
.chat-bubble-ai {
    background: rgba(30,41,59,0.7); border: 1px solid rgba(59,130,246,0.15);
    border-radius: 4px 12px 12px 12px;
    padding: 0.65rem 0.9rem; margin-bottom: 0.35rem; font-size: 0.85rem; color: #CBD5E1; line-height: 1.65;
}
.cit-chip {
    display: inline-block; background: rgba(251,191,36,0.15);
    border: 1px solid rgba(251,191,36,0.4); border-radius: 20px;
    padding: 2px 10px; font-size: 0.7rem; color: #FCD34D; cursor: pointer;
    margin: 2px; font-weight: 600;
}
.cit-chip:hover { background: rgba(251,191,36,0.28); }
.pdf-placeholder { text-align: center; padding: 3rem 1rem; color: #334155; }
.pdf-placeholder-icon { font-size: 2.5rem; margin-bottom: 0.5rem; }

/* ========== ANIMATIONS ========== */
.loading-pulse { animation: loadingPulse 1.5s ease-in-out infinite; }
@keyframes loadingPulse {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
}
@keyframes vizFadeIn {
    from { opacity: 0; transform: scale(0.98); }
    to { opacity: 1; transform: scale(1); }
}

/* ========== RESPONSIVE ========== */
@media (max-width: 1400px) { .clio-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 900px) {
    .clio-grid { grid-template-columns: 1fr; height: auto; }
    .clio-column { min-height: 400px; }
}
</style>
"""


def inject_css():
    st.markdown(MAIN_CSS, unsafe_allow_html=True)


def render_header():
    st.markdown("""
    <div class="clio-header">
        <div class="clio-logo">
            <div class="clio-logo-text">CLIO</div>
            <div class="clio-tagline">Financial Intelligence</div>
        </div>
        <div class="clio-status">
            <span class="status-indicator"></span>
            <span>System Operational</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
