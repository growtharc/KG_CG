import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

# Ensure repo root is importable when running `streamlit run ui/streamlit_app.py`.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from main import SimpleNeo4jDemo


st.set_page_config(page_title="Neo4j Ticket Context", layout="wide")
st.title("Neo4j Ticket Context Graph")
st.caption("Salesforce/Jira support ticket graph — domain-aware schema with resolution scoring.")


@st.cache_resource
def get_graph():
    try:
        return SimpleNeo4jDemo()
    except ConnectionError as e:
        st.error(f"**Neo4j connection failed**\n\n{e}")
        st.info(
            "**To fix this:**\n"
            "1. Open Neo4j Desktop and make sure your database is **Started** (green Active status)\n"
            "2. Check that `NEO4J_PASSWORD` in your `.env` file matches the database password\n"
            "3. Restart Streamlit after fixing the password"
        )
        st.stop()
    except Exception as e:
        st.error(f"**Unexpected error connecting to Neo4j:** {e}")
        st.stop()


def render_stats(stats):
    col1, col2, col3 = st.columns(3)
    col1.metric("Tickets", stats["ticket_count"])
    col2.metric("Issue Types", stats["issue_type_count"])
    col3.metric("Resolutions", stats["resolution_count"])
    col4, col5, col6 = st.columns(3)
    col4.metric("SF Objects", stats["object_count"])
    col5.metric("Actions", stats["action_count"])
    col6.metric("Similarity Links", stats["similarity_count"])


def render_context_stats(stats):
    col1, col2, col3 = st.columns(3)
    col1.metric("Context Documents", stats["document_count"])
    col2.metric("Context Pages", stats["page_count"])
    col3.metric("Context Chunks", stats["chunk_count"])
    col4, col5, col6 = st.columns(3)
    col4.metric("Context Issue Types", stats["issue_type_count"])
    col5.metric("Context SF Objects", stats["object_count"])
    col6.metric("Context Resolutions", stats["resolution_count"])


graph = get_graph()

with st.sidebar:
    st.subheader("Data Setup")
    clear_existing = st.checkbox("Clear existing graph before load", value=True)

    if st.button("Load Hardcoded Sample Tickets", use_container_width=True):
        try:
            loaded = graph.load_hardcoded_tickets(clear_existing=clear_existing)
            st.success(f"Loaded {loaded} tickets and created similarity links.")
        except Exception as exc:
            st.error(f"Load failed: {exc}")

    st.markdown("---")
    st.subheader("Load from CSV")
    default_csv = "data/jira_tickets.csv"
    csv_path = st.text_input("CSV path", value=default_csv)
    csv_limit = st.number_input("Max rows to load", min_value=1, max_value=5000, value=50, step=1)

    if st.button("Load CSV into KG", use_container_width=True):
        try:
            df = pd.read_csv(csv_path)
            if clear_existing:
                graph.clear_all()
            loaded_count = 0
            for _, row in df.head(int(csv_limit)).iterrows():
                # support both column name styles
                ticket_id = str(row.get("Issue key", row.get("issue_key", f"CSV-{loaded_count+1}")))
                summary = str(row.get("Summary", row.get("summary", "")))
                resolution = None
                if summary:
                    graph.add_ticket(ticket_id, summary, resolution)
                    loaded_count += 1
            graph.create_similarity_links()
            st.success(f"Loaded {loaded_count} tickets from CSV and created similarity links.")
        except Exception as exc:
            st.error(f"CSV load failed: {exc}")

st.subheader("Current Graph Stats")
try:
    stats = graph.get_graph_stats()
    render_stats(stats)
except Exception as exc:
    st.warning(f"Graph stats unavailable — load tickets first using the sidebar button.")

st.divider()
st.subheader("Context Graph Builder")
st.caption("Create context graph nodes from unstructured text. This does not update the KG.")

st.markdown("**Upload Unstructured Document (PDF) → Context Graph**")
st.caption("Use this to ingest RCA documents, runbooks, or any unstructured PDF. Chunks are extracted and linked to domain entities in the Context Graph.")
uploaded_pdf = st.file_uploader("Upload PDF (e.g. RCA-Onboarding-Tickets.pdf)", type=["pdf"])
pdf_document_id = st.text_input("PDF context document ID (optional)", value="")
pdf_max_chunks_per_page = st.number_input(
    "Max chunks per page", min_value=1, max_value=200, value=30, step=1
)
pdf_source = st.text_input("PDF source label", value="pdf_upload")
pdf_clear_context = st.checkbox("Clear existing context graph before PDF ingest", value=False)

if st.button("Build Context Graph From PDF", use_container_width=True):
    if uploaded_pdf is None:
        st.warning("Please upload a PDF file.")
    else:
        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(uploaded_pdf.getbuffer())
                temp_path = temp_file.name

            pdf_result = graph.build_context_graph_from_pdf(
                pdf_path=temp_path,
                document_id=pdf_document_id.strip(),
                source=pdf_source.strip() or "pdf_upload",
                max_chunks_per_page=int(pdf_max_chunks_per_page),
                clear_existing_context=pdf_clear_context,
            )

            st.success(
                f"Built context graph for document `{pdf_result['document_id']}` "
                f"with `{pdf_result['processed_chunks']}` chunks."
            )

            st.markdown("**Parsed Chunks (first 20)**")
            st.dataframe(pdf_result["parsed_chunks"][:20], use_container_width=True)

            st.markdown("**Sample Context Traces (first 10)**")
            st.dataframe(
                [
                    {
                        "chunk_id": t["chunk_id"],
                        "page_id": t["page_id"],
                        "issue_type": t["extracted"].get("issue_type"),
                        "object": t["extracted"].get("object"),
                        "resolution": t["extracted"].get("resolution"),
                    }
                    for t in pdf_result["sample_traces"]
                ],
                use_container_width=True,
            )
        except Exception as exc:
            st.error(f"PDF context build failed: {exc}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

st.markdown("---")

context_summary = st.text_area(
    "Unstructured text chunk",
    value="Customer reported that after the Q4 migration, duplicate opportunity records were created in Salesforce for the ACME Corp account. The primary opportunity (OPP-2024-001) shows $250K ARR while the duplicate (OPP-2024-002) shows $0. Sales team cannot proceed with contract renewal until this is resolved. Need to merge or delete the duplicate record and ensure data integrity across related objects including quotes and contacts.",
    height=90,
)
context_document_id = st.text_input("Context document ID (optional)", value="")
ctx_col1, ctx_col2, ctx_col3 = st.columns(3)
with ctx_col1:
    context_page_number = st.number_input("Page", min_value=1, max_value=10000, value=1, step=1)
with ctx_col2:
    context_chunk_index = st.number_input("Chunk", min_value=1, max_value=100000, value=1, step=1)
with ctx_col3:
    context_source = st.text_input("Source", value="manual")

ctx_btn1, ctx_btn2 = st.columns(2)
with ctx_btn1:
    build_context_clicked = st.button("Build Context Graph Node", use_container_width=True)
with ctx_btn2:
    clear_context_clicked = st.button("Clear Context Graph", use_container_width=True)

if build_context_clicked:
    if not context_summary.strip():
        st.warning("Please enter text to build context graph.")
    else:
        try:
            trace = graph.create_context_graph_from_summary(
                summary=context_summary.strip(),
                document_id=context_document_id.strip(),
                page_number=int(context_page_number),
                chunk_index=int(context_chunk_index),
                source=context_source.strip() or "manual",
            )
            st.session_state["last_context_trace"] = trace
            st.success(f"Context chunk created: `{trace['chunk_id']}`")
        except Exception as exc:
            st.error(f"Context graph build failed: {exc}")

if clear_context_clicked:
    try:
        graph.clear_context_graph()
        st.success("Context graph cleared.")
    except Exception as exc:
        st.error(f"Could not clear context graph: {exc}")

try:
    context_stats = graph.get_context_graph_stats()
    render_context_stats(context_stats)
except Exception as exc:
    st.warning("Context graph stats unavailable — build a context node first.")

if "last_context_trace" in st.session_state:
    last_context_trace = st.session_state["last_context_trace"]
    st.markdown("**Last Context Trace**")
    st.json(last_context_trace)

st.divider()
st.subheader("Find Similar Tickets")
ticket_summary = st.text_area(
    "New ticket summary",
    value="Urgent: Multiple duplicate payment opportunity records detected for XYZ Corp after system integration. Primary opportunity OPP-2024-156 ($180K) is correct, but duplicates OPP-2024-157 and OPP-2024-158 are causing confusion in sales pipeline reporting. Finance team blocked from processing Q1 invoices. Requires immediate cleanup of duplicate records and validation of associated payment schedules and contract terms.",
    height=100,
)
top_k = st.slider("Top K results", min_value=1, max_value=10, value=3)

if st.button("Analyze Ticket", type="primary"):
    if not ticket_summary.strip():
        st.warning("Please enter a ticket summary.")
    else:
        try:
            result = graph.query_similar_tickets(ticket_summary.strip(), top_k=int(top_k))
            extracted = result["extracted"]

            st.markdown("**Extracted Info**")
            e1, e2, e3, e4 = st.columns(4)
            e1.write(f"Action: `{extracted['action']}`")
            e2.write(f"Object: `{extracted['object']}`")
            e3.write(f"Issue Type: `{extracted['issue_type']}`")
            e4.write(f"Resolution: `{extracted['resolution']}`")

            st.markdown("**Routing Suggestion**")
            st.info(result["routing"])

            ranked = result.get("ranked_resolutions", [])
            st.markdown("**Ranked Resolution Suggestions**")
            if ranked:
                for i, r in enumerate(ranked, 1):
                    with st.expander(f"{i}. {r['resolution']} — score: {r['score']}", expanded=(i == 1)):
                        st.write(r["explanation"])
                        st.write(f"Supporting tickets: `{', '.join(r['supporting_tickets'])}`")
            else:
                st.write("No resolution suggestions found.")

            st.markdown("**Issue Type Matches**")
            if result["exact_matches"]:
                st.dataframe(result["exact_matches"], use_container_width=True)
            else:
                st.write("No issue type matches found.")

            st.markdown("**Action Matches**")
            if result["action_matches"]:
                st.dataframe(result["action_matches"], use_container_width=True)
            else:
                st.write("No action matches found.")
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")

st.divider()
st.subheader("Context -> Knowledge Graph Flow")
st.caption("Insert one ticket and inspect how extracted context is written into Neo4j.")

st.markdown(
    "**Suggested test ticket summary:** `Post-migration data cleanup required for enterprise customer account with multiple duplicate records affecting sales operations`"
)

trace_ticket_id = st.text_input(
    "Optional ticket ID (leave empty to auto-generate)", value=""
)
trace_summary = st.text_area(
    "Ticket summary for context -> KG trace",
    value="Post-migration issue: Customer Success team reports that the enterprise account for ACME Industries has duplicate opportunity records created during the Salesforce data migration from legacy CRM. The duplicate opportunities (3 total) are causing incorrect revenue forecasting and preventing the renewal workflow from completing. Primary opportunity shows correct $500K ARR, but duplicates show partial data. Need to identify the canonical record, merge or delete duplicates, and verify all related objects (contacts, quotes, activities) are properly linked.",
    height=90,
)

if st.button("Trace Context to KG"):
    if not trace_summary.strip():
        st.warning("Please enter a ticket summary.")
    else:
        try:
            trace = graph.add_ticket_with_trace(
                summary=trace_summary.strip(),
                ticket_id=trace_ticket_id.strip(),
            )

            st.success(f"Ticket inserted: `{trace['ticket_id']}`")
            st.markdown("**Extracted Context**")
            c1, c2, c3, c4 = st.columns(4)
            c1.write(f"Action: `{trace['extracted']['action']}`")
            c2.write(f"Object: `{trace['extracted']['object']}`")
            c3.write(f"Issue Type: `{trace['extracted']['issue_type']}`")
            c4.write(f"Resolution: `{trace['extracted']['resolution']}`")

            st.markdown("**Routing Decision**")
            st.info(trace["routing"])

            st.markdown("**Cypher Write Steps Used**")
            for i, query in enumerate(trace["write_cypher"], start=1):
                st.code(query, language="cypher")

            st.markdown("**Created / Linked KG Records For This Ticket**")
            if trace["created_links"]:
                st.dataframe(trace["created_links"], use_container_width=True)
            else:
                st.write("No outgoing links found for this ticket.")
        except Exception as exc:
            st.error(f"Trace failed: {exc}")

st.divider()
st.subheader("Cypher Result Panel")
st.caption("Run a Cypher query and inspect returned rows.")

cypher_query = st.text_area(
    "Cypher query",
    value="MATCH (n)-[r]->(m)\nRETURN labels(n) AS source_labels, n.id AS source_id, n.name AS source_name,\n       type(r) AS relationship,\n       labels(m) AS target_labels, m.id AS target_id, m.name AS target_name\nLIMIT 25",
    height=120,
)

if st.button("Run Cypher"):
    query = cypher_query.strip()
    if not query:
        st.warning("Please enter a Cypher query.")
    else:
        try:
            with graph.driver.session() as session:
                result = session.run(query)
                rows = [record.data() for record in result]
                summary = result.consume()

            st.write(
                f"Returned `{len(rows)}` rows "
                f"(available after: `{summary.result_available_after} ms`, "
                f"consumed after: `{summary.result_consumed_after} ms`)."
            )

            if rows:
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("Query executed successfully, but no rows were returned.")
        except Exception as exc:
            st.error(f"Cypher query failed: {exc}")
