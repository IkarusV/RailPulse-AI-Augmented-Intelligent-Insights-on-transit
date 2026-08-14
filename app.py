import pandas as pd
import streamlit as st

from assistant import QuestionNotAnswerable, answer_question
from config import DATABASE_PATH
from database import DatabaseError
from llm_client import LLMError
from scripts.build_database import build_database
from sql_guard import UnsafeQuery


# Step 1: configure the page and visual theme

st.set_page_config(
    page_title="RailPulse AI",
    page_icon="🚉",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --navy-950: #050c16;
        --navy-900: #07111f;
        --navy-850: #091827;
        --navy-800: #0d1d2e;
        --navy-700: #15324a;
        --rail-blue: #37b7ff;
        --signal-yellow: #ffd54a;
        --text-main: #eaf2f8;
        --text-muted: #9fb2c3;
    }
    .stApp {
        background:
            radial-gradient(circle at 85% 8%, rgba(55, 183, 255, .10), transparent 28rem),
            linear-gradient(180deg, var(--navy-950) 0%, var(--navy-900) 100%);
        color: var(--text-main);
    }
    [data-testid="stHeader"] { background: rgba(5, 12, 22, .72); backdrop-filter: blur(10px); }
    .block-container { max-width: 1100px; padding-top: 2.5rem; }
    .rail-hero {
        position: relative;
        overflow: hidden;
        background:
            linear-gradient(105deg, rgba(6, 25, 43, .98), rgba(8, 67, 105, .94)),
            repeating-linear-gradient(90deg, transparent 0 90px, rgba(255,255,255,.025) 90px 91px);
        border: 1px solid rgba(55, 183, 255, .28);
        border-radius: 20px;
        color: white;
        padding: 2rem 2.2rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 20px 55px rgba(0, 0, 0, .38), inset 0 1px rgba(255,255,255,.06);
    }
    .rail-hero::after {
        content: "";
        position: absolute;
        width: 260px;
        height: 260px;
        border: 32px solid rgba(55, 183, 255, .08);
        border-radius: 50%;
        right: -90px;
        top: -110px;
    }
    .rail-kicker { color: var(--signal-yellow); font-size: .78rem; font-weight: 800; letter-spacing: .14em; }
    .rail-title { font-size: 2.5rem; font-weight: 780; margin: .25rem 0 .4rem; }
    .rail-subtitle { color: #d9e8f4; font-size: 1rem; max-width: 720px; }
    .scope-card {
        border: 1px solid rgba(102, 151, 187, .22);
        border-radius: 14px;
        background: linear-gradient(145deg, rgba(15, 35, 53, .94), rgba(9, 24, 39, .94));
        padding: .95rem 1.1rem;
        min-height: 105px;
        box-shadow: 0 10px 24px rgba(0, 0, 0, .18);
    }
    .scope-label { color: var(--text-muted); font-size: .75rem; text-transform: uppercase; letter-spacing: .08em; }
    .scope-value { color: var(--text-main); font-size: 1.08rem; font-weight: 750; margin-top: .3rem; }
    .scope-card:hover { border-color: rgba(55, 183, 255, .48); transform: translateY(-1px); transition: .18s ease; }
    [data-testid="stChatMessage"] {
        background: rgba(13, 29, 46, .74);
        border: 1px solid rgba(102, 151, 187, .18);
        border-radius: 15px;
        padding: .45rem .65rem;
        margin-bottom: .65rem;
    }
    [data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(5, 16, 28, .65);
        border-color: rgba(55, 183, 255, .20);
    }
    [data-testid="stDataFrame"] { border: 1px solid rgba(55, 183, 255, .18); border-radius: 10px; overflow: hidden; }
    [data-testid="stExpander"] { background: rgba(9, 24, 39, .68); border-color: rgba(102, 151, 187, .20); }
    [data-testid="stForm"] {
        background: linear-gradient(145deg, rgba(15, 35, 53, .94), rgba(9, 24, 39, .94));
        border: 1px solid rgba(55, 183, 255, .24);
        border-radius: 16px;
        padding: 1rem;
        margin-bottom: 1.1rem;
    }
    [data-testid="stTextInput"] input {
        background: rgba(5, 16, 28, .88);
        border-color: rgba(102, 151, 187, .32);
        color: var(--text-main);
    }
    .fineprint { color: var(--text-muted); font-size: .82rem; }
    .stButton > button {
        border-radius: 999px;
        border-color: rgba(55, 183, 255, .30);
        background: rgba(13, 40, 61, .82);
        color: #dff3ff;
    }
    .stButton > button:hover { border-color: var(--rail-blue); color: white; background: rgba(21, 67, 98, .95); }
    h1, h2, h3, h4 { color: var(--text-main); }
    p, li { color: #cfdae4; }
    hr { border-color: rgba(102, 151, 187, .15); }
    @media (max-width: 700px) {
        .rail-title { font-size: 1.8rem; }
        .rail-hero { padding: 1.5rem; }
        .block-container { padding-top: 1.2rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# Step 2: render reusable interface sections

def render_hero():
    """Show the project title and the main data-scope cards."""

    st.markdown(
        """
        <section class="rail-hero">
            <div class="rail-kicker">RAILPULSE OPERATIONS INTELLIGENCE</div>
            <div class="rail-title">Ask the departure data.</div>
            <div class="rail-subtitle">
                A guarded text-to-SQL assistant for Brussels-Central. It translates
                operational questions into read-only queries, shows the evidence,
                and returns a concise station-management recommendation.
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    columns = st.columns(3)
    cards = [
        ("Scope", "211 unique departures"),
        ("Live window", "09:00-12:59 · 2 Wednesdays"),
        ("Safety", "Read-only snapshot · 100 row cap"),
    ]
    for column, (label, value) in zip(columns, cards):
        with column:
            st.markdown(
                f'<div class="scope-card"><div class="scope-label">{label}</div>'
                f'<div class="scope-value">{value}</div></div>',
                unsafe_allow_html=True,
            )


def render_result(result):
    """Show one answer with its evidence table and validated SQL."""

    with st.container(border=True):
        st.markdown(f"#### {result['title']}")
        st.markdown(result["answer"])

    if result["rows"]:
        frame = pd.DataFrame(result["rows"], columns=result["columns"])
        st.dataframe(frame, width="stretch", hide_index=True)
    else:
        st.info("The validated query returned no matching records.")

    with st.expander("Inspect the validated SQL"):
        st.code(result["sql"], language="sql")
        st.caption(
            "The query passed application validation and ran against a database "
            "opened in read-only, query-only mode."
        )


# Step 3: check local data before accepting questions

render_hero()

if not DATABASE_PATH.exists():
    with st.spinner("Preparing the RailPulse data snapshot..."):
        try:
            build_database()
        except Exception as error:
            st.error(f"The data snapshot could not be prepared: {error}")
            st.stop()

st.markdown("### Ask an operational question")
suggestions = [
    "Which platform had the worst average delay?",
    "What was the overall on-time rate?",
    "Which train class caused the most delayed minutes?",
    "Show the five most delayed departures.",
]

# Step 4: keep chat history across Streamlit reruns

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = ""

with st.form("railpulse-question", clear_on_submit=True):
    form_columns = st.columns([5, 1])
    with form_columns[0]:
        typed_question = st.text_input(
            "Your question",
            placeholder="Example: Which destination accumulated the most delay?",
            label_visibility="collapsed",
        )
    with form_columns[1]:
        submitted = st.form_submit_button(
            "Ask RailPulse",
            type="primary",
            width="stretch",
        )

st.caption("Or start from one of these examples:")
suggestion_columns = st.columns(2)
for index, suggestion in enumerate(suggestions):
    with suggestion_columns[index % 2]:
        if st.button(suggestion, width="stretch"):
            st.session_state.pending_question = suggestion

# Step 5: redraw earlier messages

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
        elif "error" in message:
            st.warning(message["error"])
        else:
            render_result(message["result"])

# Step 6: process either typed text or an example question

question = st.session_state.pending_question or (typed_question if submitted else "")
if question:
    st.session_state.pending_question = ""
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    result = None
    error_message = None
    with st.spinner("Planning, validating, and running a read-only query..."):
        try:
            result = answer_question(question)
        except QuestionNotAnswerable as error:
            error_message = str(error)
        except UnsafeQuery as error:
            error_message = f"The generated query was blocked by the safety layer: {error}"
        except (DatabaseError, LLMError) as error:
            error_message = str(error)
    if error_message:
        st.session_state.messages.append({"role": "assistant", "error": error_message})
        with st.chat_message("assistant"):
            st.warning(error_message)
    if result:
        st.session_state.messages.append({"role": "assistant", "result": result})
        with st.chat_message("assistant"):
            render_result(result)

# Step 7: show scope notes beneath the conversation

st.divider()
with st.expander("Data scope and limitations"):
    st.markdown(
        """
        - Source: iRail liveboard observations collected through the RailPulse Azure pipeline.
        - Grain: one unique departure using its latest collected observation.
        - Coverage: Brussels-Central, 29 July and 5 August 2026, 09:00-12:59.
        - No P services or cancellations were observed in this midday sample.
        - This assistant must not generalize the sample into permanent network-wide performance.
        """
    )

st.markdown(
    '<div class="fineprint">Generated answers are grounded in validated SQL results. '
    "Operational recommendations remain decision support, not automated control.</div>",
    unsafe_allow_html=True,
)
