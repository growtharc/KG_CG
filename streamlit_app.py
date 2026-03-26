import streamlit as st

from main import SimpleNeo4jDemo


st.set_page_config(page_title="Neo4j Ticket Context", layout="wide")
st.title("Neo4j Ticket Context Graph")
st.caption("Basic Streamlit UI for loading sample tickets and finding similar tickets.")


@st.cache_resource
def get_graph():
    return SimpleNeo4jDemo()


def render_stats(stats):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tickets", stats["ticket_count"])
    col2.metric("Actions", stats["action_count"])
    col3.metric("Objects", stats["object_count"])
    col4.metric("Similarity Links", stats["similarity_count"])


def render_context_stats(stats):
    col1, col2, col3 = st.columns(3)
    col1.metric("Context Documents", stats["document_count"])
    col2.metric("Context Pages", stats["page_count"])
    col3.metric("Context Chunks", stats["chunk_count"])
    col4, col5, col6 = st.columns(3)
    col4.metric("Context Actions", stats["action_count"])
    col5.metric("Context Objects", stats["object_count"])
    col6.metric("Context Problems", stats["problem_count"])


graph = get_graph()

with st.sidebar:
    st.subheader("Data Setup")
    csv_path = st.text_input("CSV path", value="Jira last 6 months.csv")
    limit = st.number_input("Sample size", min_value=1, max_value=5000, value=10, step=1)
    clear_existing = st.checkbox("Clear existing graph before load", value=True)

    if st.button("Load Sample Tickets", use_container_width=True):
        try:
            loaded = graph.load_sample_tickets(
                csv_path=csv_path,
                limit=int(limit),
                clear_existing=clear_existing,
            )
            st.success(f"Loaded {loaded} tickets and created similarity links.")
        except Exception as exc:
            st.error(f"Load failed: {exc}")

st.subheader("Current Graph Stats")
try:
    stats = graph.get_graph_stats()
    render_stats(stats)
except Exception as exc:
    st.warning(f"Could not fetch graph stats yet: {exc}")

st.divider()
st.subheader("Context Graph Builder")
st.caption("Create context graph nodes from unstructured text. This does not update the KG.")

context_summary = st.text_area(
    "Unstructured text chunk",
    value="Delete duplicate opportunity record for ACME account",
    height=90,
)
context_document_id = st.text_input(
    "Context document ID (optional)", value=""
)
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
    st.warning(f"Could not fetch context graph stats: {exc}")

if "last_context_trace" in st.session_state:
    last_context_trace = st.session_state["last_context_trace"]
    st.markdown("**Last Context Trace**")
    st.json(last_context_trace)

st.divider()
st.subheader("Find Similar Tickets")
ticket_summary = st.text_area(
    "New ticket summary",
    value="Delete duplicate payment opportunity for XYZ Corp",
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
            e1, e2, e3 = st.columns(3)
            e1.write(f"Action: `{extracted['action']}`")
            e2.write(f"Object: `{extracted['object']}`")
            e3.write(f"Problem: `{extracted['problem']}`")

            st.markdown("**Routing Suggestion**")
            st.info(result["routing"])

            st.markdown("**Exact Matches (Same Action + Object)**")
            if result["exact_matches"]:
                st.dataframe(result["exact_matches"], use_container_width=True)
            else:
                st.write("No exact matches found.")

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
    "**Suggested test ticket summary:** `Delete duplicate opportunity record for ACME account`"
)

trace_ticket_id = st.text_input(
    "Optional ticket ID (leave empty to auto-generate)", value=""
)
trace_summary = st.text_area(
    "Ticket summary for context -> KG trace",
    value="Delete duplicate opportunity record for ACME account",
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
            c1, c2, c3 = st.columns(3)
            c1.write(f"Action: `{trace['extracted']['action']}`")
            c2.write(f"Object: `{trace['extracted']['object']}`")
            c3.write(f"Problem: `{trace['extracted']['problem']}`")

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
    value="MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 25",
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
