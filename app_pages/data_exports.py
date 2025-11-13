import streamlit as st
import pandas as pd
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime
from services.db_helper import get_connection, get_all_cycles


st.title("Data Exports")
st.markdown("Export feedback and nomination data for selected cycles.")

# Load cycles
cycles = get_all_cycles() or []

if not cycles:
    st.warning("No cycles found.")
    st.stop()

# Build selector
cycle_options = [
    {
        "label": f"{c.get('cycle_display_name') or c.get('cycle_name')} ({c.get('cycle_year', '')} {c.get('cycle_quarter', '')})",
        "id": c["cycle_id"],
    }
    for c in cycles
]

default_ids = [opt["id"] for opt in cycle_options]

selected_labels = st.multiselect(
    "Select cycles:",
    options=[opt["label"] for opt in cycle_options],
    default=[opt["label"] for opt in cycle_options],
)

label_to_id = {opt["label"]: opt["id"] for opt in cycle_options}
selected_ids = [label_to_id[lbl] for lbl in selected_labels]

if not selected_ids:
    st.info("Select at least one cycle to enable exports.")
    st.stop()

conn = get_connection()


def export_feedback(selected_cycle_ids):
    # Convert cycle IDs to comma-separated string for LibSQL compatibility
    cycle_ids_str = ",".join(str(cycle_id) for cycle_id in selected_cycle_ids)
    query = f"""
        SELECT 
            fr.request_id,
            rc.cycle_display_name,
            fr.cycle_id,
            req.first_name || ' ' || req.last_name as requester_name,
            req.email as requester_email,
            req.vertical as requester_vertical,
            COALESCE(rev.first_name || ' ' || rev.last_name, 'External Reviewer') as reviewer_name,
            COALESCE(rev.email, fr.external_reviewer_email) as reviewer_email,
            fr.relationship_type,
            fq.question_text,
            fq.question_type,
            resp.rating_value,
            resp.response_value,
            resp.submitted_at,
            fr.completed_at
        FROM feedback_requests fr
        JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
        JOIN users req ON fr.requester_id = req.user_type_id
        LEFT JOIN users rev ON fr.reviewer_id = rev.user_type_id
        JOIN feedback_responses resp ON fr.request_id = resp.request_id
        JOIN feedback_questions fq ON resp.question_id = fq.question_id
        WHERE fr.workflow_state = 'completed' AND fr.cycle_id IN ({cycle_ids_str})
        ORDER BY rc.cycle_display_name, fr.request_id, fq.question_text
    """
    rows = conn.execute(query).fetchall()
    cols = [
        "request_id",
        "cycle_display_name",
        "cycle_id",
        "requester_name",
        "requester_email",
        "requester_vertical",
        "reviewer_name",
        "reviewer_email",
        "relationship_type",
        "question_text",
        "question_type",
        "rating_value",
        "response_value",
        "response_submitted_at",
        "request_completed_at",
    ]
    df = pd.DataFrame(rows, columns=cols)
    return df


def export_nominations(selected_cycle_ids):
    # Convert cycle IDs to comma-separated string for LibSQL compatibility
    cycle_ids_str = ",".join(str(cycle_id) for cycle_id in selected_cycle_ids)
    query = f"""
        SELECT 
            fr.request_id,
            rc.cycle_display_name,
            fr.cycle_id,
            fr.created_at,
            req.first_name || ' ' || req.last_name as requester_name,
            req.email as requester_email,
            COALESCE(rev.first_name || ' ' || rev.last_name, 'External Reviewer') as reviewer_name,
            COALESCE(rev.email, fr.external_reviewer_email) as reviewer_email,
            fr.relationship_type,
            fr.workflow_state as status,
            fr.manager_decision as approval_status,
            fr.manager_decision_date as approval_date,
            fr.manager_rejection_reason as rejection_reason,
            fr.reviewer_status,
            fr.reviewer_response_date,
            fr.reviewer_rejection_reason,
            fr.completed_at
        FROM feedback_requests fr
        JOIN review_cycles rc ON fr.cycle_id = rc.cycle_id
        JOIN users req ON fr.requester_id = req.user_type_id
        LEFT JOIN users rev ON fr.reviewer_id = rev.user_type_id
        WHERE fr.cycle_id IN ({cycle_ids_str})
        ORDER BY rc.cycle_display_name, fr.created_at
    """
    rows = conn.execute(query).fetchall()
    cols = [
        "request_id",
        "cycle_display_name",
        "cycle_id",
        "created_at",
        "requester_name",
        "requester_email",
        "reviewer_name",
        "reviewer_email",
        "relationship_type",
        "status",
        "approval_status", 
        "approval_date",
        "rejection_reason",
        "reviewer_status",
        "reviewer_response_date",
        "reviewer_rejection_reason",
        "completed_at",
    ]
    df = pd.DataFrame(rows, columns=cols)
    return df


col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Export Feedback Data (CSV/XLSX)"):
        df = export_feedback(selected_ids)
        if df.empty:
            st.info("No completed feedback found for the selected cycles.")
        else:
            # CSV
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Feedback CSV",
                data=csv,
                file_name=f"feedback_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )

            # Excel
            xls = BytesIO()
            with pd.ExcelWriter(xls, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Feedback")
            xls.seek(0)
            st.download_button(
                label="Download Feedback Excel",
                data=xls.getvalue(),
                file_name=f"feedback_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

with col2:
    if st.button("Export Nominations (CSV/XLSX)"):
        df = export_nominations(selected_ids)
        if df.empty:
            st.info("No nominations found for the selected cycles.")
        else:
            # CSV
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Nominations CSV",
                data=csv,
                file_name=f"nominations_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )

            # Excel
            xls = BytesIO()
            with pd.ExcelWriter(xls, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Nominations")
            xls.seek(0)
            st.download_button(
                label="Download Nominations Excel",
                data=xls.getvalue(),
                file_name=f"nominations_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

with col3:
    if st.button("Export All (ZIP)"):
        df_feedback = export_feedback(selected_ids)
        df_noms = export_nominations(selected_ids)
        if df_feedback.empty and df_noms.empty:
            st.info("No data found for the selected cycles.")
        else:
            buffer = BytesIO()
            with ZipFile(buffer, "w", ZIP_DEFLATED) as zf:
                if not df_feedback.empty:
                    zf.writestr(
                        "feedback.csv",
                        df_feedback.to_csv(index=False),
                    )
                if not df_noms.empty:
                    zf.writestr(
                        "nominations.csv",
                        df_noms.to_csv(index=False),
                    )
            buffer.seek(0)
            st.download_button(
                label="Download All (ZIP)",
                data=buffer,
                file_name=f"all_exports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
            )
