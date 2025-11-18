import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from html import escape

_STYLE_FLAG = "_feedback_styles_applied"


def ensure_feedback_styles():
    """Inject shared CSS for feedback cards once per session."""
    if st.session_state.get(_STYLE_FLAG):
        return
    st.markdown(
        """
        <style>
        .feedback-card {
            padding: 0.9rem 1rem;
            background: #f8f9fc;
            border-radius: 8px;
            margin-bottom: 0.6rem;
            border: 1px solid rgba(30,71,150,0.08);
        }
        .question-text {
            font-weight: 600;
            color: #1E3968;
            margin-bottom: 0.35rem;
        }
        .rating-row {
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }
        .rating-bar {
            flex: 1;
            height: 8px;
            background: #e4e8f1;
            border-radius: 999px;
            overflow: hidden;
        }
        .rating-fill {
            height: 8px;
            background: #1E4796;
        }
        .rating-score {
            font-weight: 600;
            color: #1E4796;
            min-width: 45px;
            text-align: right;
        }
        .text-response {
            color: #2c2f36;
            line-height: 1.5;
        }
        .feedback-empty {
            color: #737a91;
            font-style: italic;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state[_STYLE_FLAG] = True


def render_rating_card(question_text: str, rating_value: int | None):
    """Display rating question nicely."""
    ensure_feedback_styles()
    rating = rating_value or 0
    percent = max(0, min(100, int((rating / 5) * 100)))
    score_label = f"{rating}/5" if rating_value is not None else "–/5"
    st.markdown(
        f"""
        <div class="feedback-card">
            <div class="question-text">{escape(question_text)}</div>
            <div class="rating-row">
                <div class="rating-bar"><div class="rating-fill" style="width:{percent}%;"></div></div>
                <div class="rating-score">{score_label}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_text_card(question_text: str, response_value: str | None):
    """Display text response with consistent styling."""
    ensure_feedback_styles()
    if response_value:
        body = escape(response_value)
    else:
        body = "<span class='feedback-empty'>No response provided</span>"
    st.markdown(
        f"""
        <div class="feedback-card">
            <div class="question-text">{escape(question_text)}</div>
            <div class="text-response">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_feedback_excel(rows: list[dict], filename_prefix: str, sheet_name: str = "Feedback"):
    """Return (bytes, filename) for download_button consumption."""
    if not rows:
        return None, None
    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        worksheet = writer.sheets[sheet_name]
        for column in worksheet.columns:
            max_length = 0
            column_cells = [cell for cell in column]
            for cell in column_cells:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_cells[0].column_letter].width = adjusted_width
    output.seek(0)
    filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return output.getvalue(), filename
