from collections import defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class KnowledgeGraphService:
    HARDCODED_TICKETS: List[Dict] = [
        {
            "id": "SD-75162",
            "summary": "Delete duplicate opps (nextplumbingandair)",
            "resolution": "DeleteRecord",
        },
        {
            "id": "SD-74868",
            "summary": "Please Delete Duplicate Payments Opportunity for Reactive Plumbing Services",
            "resolution": "DeleteRecord",
        },
        {
            "id": "SD-74668",
            "summary": "Delayed Salesforce access request",
            "resolution": "GrantAccess",
        },
        {
            "id": "SD-73956",
            "summary": "I need access to ServiceTitan salesforce",
            "resolution": "GrantAccess",
        },
        {
            "id": "SD-73829",
            "summary": "hoping to get this OB record churned",
            "resolution": "ChurnOBRecord",
        },
        {
            "id": "SD-72514",
            "summary": "Need Onboarding Record rolled back to Pending Underwriting",
            "resolution": "UpdateRecord",
        },
        {
            "id": "SD-71406",
            "summary": "Please delete OB record - created in Error",
            "resolution": "DeleteOBRecord",
        },
        {
            "id": "SD-73691",
            "summary": "Please create a Payment Opportunity for Harwich Port Heating and Cooling",
            "resolution": "CreateOpportunity",
        },
        {
            "id": "SD-71772",
            "summary": "Update account status to success",
            "resolution": "UpdateRecord",
        },
        {
            "id": "SD-65577",
            "summary": "Flip Case Status to Contract Updated",
            "resolution": "UpdateRecord",
        },
    ]

    def __init__(
        self,
        driver,
        extract_info_fn: Callable[[str], Dict],
        get_routing_fn: Callable[[Dict], str],
    ):
        self.driver = driver
        self.extract_info = extract_info_fn
        self.get_routing = get_routing_fn

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def ensure_kg_schema(self):
        """Create uniqueness constraints for all KG node types."""
        constraints = [
            "CREATE CONSTRAINT ticket_id IF NOT EXISTS FOR (t:Ticket) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT issue_type_name IF NOT EXISTS FOR (i:IssueType) REQUIRE i.name IS UNIQUE",
            "CREATE CONSTRAINT sf_object_name IF NOT EXISTS FOR (o:SalesforceObject) REQUIRE o.name IS UNIQUE",
            "CREATE CONSTRAINT action_name IF NOT EXISTS FOR (a:Action) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT resolution_name IF NOT EXISTS FOR (r:Resolution) REQUIRE r.name IS UNIQUE",
        ]
        with self.driver.session() as session:
            for stmt in constraints:
                session.run(stmt)

    def clear_all(self):
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_ticket(self, ticket_id: str, summary: str, resolution: Optional[str] = None):
        info = self.extract_info(summary)
        effective_resolution = resolution or info.get("resolution")

        with self.driver.session() as session:
            session.run(
                "MERGE (t:Ticket {id: $id}) SET t.summary = $summary",
                id=ticket_id,
                summary=summary,
            )
            if info.get("action"):
                session.run(
                    """
                    MATCH (t:Ticket {id: $tid})
                    MERGE (a:Action {name: $name})
                    MERGE (t)-[:HAS_ACTION]->(a)
                    """,
                    tid=ticket_id,
                    name=info["action"],
                )
            if info.get("object"):
                session.run(
                    """
                    MATCH (t:Ticket {id: $tid})
                    MERGE (o:SalesforceObject {name: $name})
                    MERGE (t)-[:INVOLVES_OBJECT]->(o)
                    """,
                    tid=ticket_id,
                    name=info["object"],
                )
            if info.get("issue_type"):
                session.run(
                    """
                    MATCH (t:Ticket {id: $tid})
                    MERGE (i:IssueType {name: $name})
                    MERGE (t)-[:HAS_ISSUE_TYPE]->(i)
                    """,
                    tid=ticket_id,
                    name=info["issue_type"],
                )
            if effective_resolution:
                session.run(
                    """
                    MATCH (t:Ticket {id: $tid})
                    MERGE (r:Resolution {name: $name})
                    MERGE (t)-[:RESOLVED_BY]->(r)
                    """,
                    tid=ticket_id,
                    name=effective_resolution,
                )

    def add_ticket_with_trace(self, summary: str, ticket_id: str = "") -> Dict:
        final_id = ticket_id.strip() or f"DEMO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        extracted = self.extract_info(summary)
        self.add_ticket(final_id, summary)

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Ticket {id: $tid})
                OPTIONAL MATCH (t)-[r]->(x)
                RETURN t.id AS ticket_id,
                       t.summary AS ticket_summary,
                       type(r) AS relationship,
                       labels(x) AS target_labels,
                       x.name AS target_name
                ORDER BY relationship
                """,
                tid=final_id,
            )
            rows = [dict(record) for record in result]

        return {
            "ticket_id": final_id,
            "summary": summary,
            "extracted": extracted,
            "routing": self.get_routing(extracted),
            "write_cypher": [
                "MERGE (t:Ticket {id: $id}) SET t.summary = $summary",
                "MERGE (a:Action {name: $action}) MERGE (t)-[:HAS_ACTION]->(a)",
                "MERGE (o:SalesforceObject {name: $object}) MERGE (t)-[:INVOLVES_OBJECT]->(o)",
                "MERGE (i:IssueType {name: $issue_type}) MERGE (t)-[:HAS_ISSUE_TYPE]->(i)",
                "MERGE (r:Resolution {name: $resolution}) MERGE (t)-[:RESOLVED_BY]->(r)",
            ],
            "created_links": rows,
        }

    def create_similarity_links(self):
        """Create SIMILAR_TO edges for tickets sharing IssueType or SalesforceObject.
        Also create statistical TYPICALLY_INVOLVES and TYPICALLY_RESOLVES_WITH edges."""
        with self.driver.session() as session:
            # SIMILAR_TO on shared IssueType
            session.run(
                """
                MATCH (t1:Ticket)-[:HAS_ISSUE_TYPE]->(i:IssueType)<-[:HAS_ISSUE_TYPE]-(t2:Ticket)
                WHERE t1.id < t2.id
                MERGE (t1)-[:SIMILAR_TO {reason: 'Same IssueType'}]->(t2)
                """
            )
            # SIMILAR_TO on shared SalesforceObject
            session.run(
                """
                MATCH (t1:Ticket)-[:INVOLVES_OBJECT]->(o:SalesforceObject)<-[:INVOLVES_OBJECT]-(t2:Ticket)
                WHERE t1.id < t2.id
                MERGE (t1)-[:SIMILAR_TO {reason: 'Same SalesforceObject'}]->(t2)
                """
            )
            # Statistical: IssueType -> SalesforceObject
            session.run(
                """
                MATCH (t:Ticket)-[:HAS_ISSUE_TYPE]->(i:IssueType)
                MATCH (t)-[:INVOLVES_OBJECT]->(o:SalesforceObject)
                MERGE (i)-[:TYPICALLY_INVOLVES]->(o)
                """
            )
            # Statistical: IssueType -> Resolution
            session.run(
                """
                MATCH (t:Ticket)-[:HAS_ISSUE_TYPE]->(i:IssueType)
                MATCH (t)-[:RESOLVED_BY]->(r:Resolution)
                MERGE (i)-[:TYPICALLY_RESOLVES_WITH]->(r)
                """
            )

    def load_hardcoded_tickets(self, clear_existing: bool = True) -> int:
        """Load the 10 hardcoded Salesforce/Jira sample tickets."""
        self.ensure_kg_schema()
        if clear_existing:
            self.clear_all()
        for ticket in self.HARDCODED_TICKETS:
            self.add_ticket(ticket["id"], ticket["summary"], ticket["resolution"])
        self.create_similarity_links()
        return len(self.HARDCODED_TICKETS)

    # Keep backward-compat shim so existing callers don't break immediately
    def load_sample_tickets(
        self,
        csv_path: str = "",
        limit: int = 10,
        clear_existing: bool = True,
    ) -> int:
        return self.load_hardcoded_tickets(clear_existing=clear_existing)

    # ------------------------------------------------------------------
    # Scoring engine
    # ------------------------------------------------------------------

    def _fetch_all_tickets(self) -> List[Dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Ticket)
                OPTIONAL MATCH (t)-[:HAS_ACTION]->(a:Action)
                OPTIONAL MATCH (t)-[:INVOLVES_OBJECT]->(o:SalesforceObject)
                OPTIONAL MATCH (t)-[:HAS_ISSUE_TYPE]->(i:IssueType)
                OPTIONAL MATCH (t)-[:RESOLVED_BY]->(r:Resolution)
                RETURN t.id AS id,
                       t.summary AS summary,
                       a.name AS action,
                       o.name AS object,
                       i.name AS issue_type,
                       r.name AS resolution
                """
            )
            return [dict(rec) for rec in result]

    def score_and_rank(self, summary: str, top_k: int = 3) -> List[Dict]:
        """Return ranked resolution suggestions for a new ticket summary."""
        stored = self._fetch_all_tickets()
        if not stored:
            return []

        query_info = self.extract_info(summary)
        summaries = [t["summary"] for t in stored]

        # TF-IDF top-3
        tfidf_top_ids = set()
        try:
            vec = TfidfVectorizer(stop_words="english")
            matrix = vec.fit_transform(summaries)
            query_vec = vec.transform([summary])
            scores = cosine_similarity(query_vec, matrix)[0]
            top3_indices = scores.argsort()[-3:][::-1]
            tfidf_top_ids = {stored[i]["id"] for i in top3_indices}
        except Exception:
            pass

        # Count resolution frequency across all stored tickets
        res_freq: Dict[str, int] = defaultdict(int)
        for t in stored:
            if t["resolution"]:
                res_freq[t["resolution"]] += 1

        # Score each stored ticket
        ticket_scores: Dict[str, Dict] = {}
        for t in stored:
            score = 0.0
            signals = []

            if query_info.get("issue_type") and t["issue_type"] == query_info["issue_type"]:
                score += 4
                signals.append(f"issue_type match ({t['issue_type']})")
            if query_info.get("object") and t["object"] == query_info["object"]:
                score += 3
                signals.append(f"object match ({t['object']})")
            if query_info.get("action") and t["action"] == query_info["action"]:
                score += 3
                signals.append(f"action match ({t['action']})")
            if t["id"] in tfidf_top_ids:
                score += 5
                signals.append("text similarity (TF-IDF top-3)")
            if t["resolution"] and res_freq[t["resolution"]] >= 2:
                score += 2
                signals.append(f"common resolution ({t['resolution']})")

            if score > 0 and t["resolution"]:
                ticket_scores[t["id"]] = {
                    "resolution": t["resolution"],
                    "score": score,
                    "ticket_id": t["id"],
                    "signals": signals,
                }

        # Group by resolution
        grouped: Dict[str, Dict] = {}
        for tid, data in ticket_scores.items():
            res = data["resolution"]
            if res not in grouped:
                grouped[res] = {
                    "resolution": res,
                    "score": 0.0,
                    "supporting_tickets": [],
                    "explanation": "",
                }
            grouped[res]["score"] += data["score"]
            grouped[res]["supporting_tickets"].append(tid)

        # Build explanation for each group
        for res, grp in grouped.items():
            supporting = grp["supporting_tickets"]
            all_signals = []
            for tid in supporting:
                all_signals.extend(ticket_scores[tid]["signals"])
            unique_signals = list(dict.fromkeys(all_signals))
            grp["explanation"] = (
                f"Resolution '{res}' suggested based on: "
                + ", ".join(unique_signals[:4])
                + f". Supported by tickets: {', '.join(supporting)}."
            )

        ranked = sorted(grouped.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query_similar_tickets(self, new_ticket_summary: str, top_k: int = 3) -> Dict:
        new_info = self.extract_info(new_ticket_summary)
        ranked = self.score_and_rank(new_ticket_summary, top_k=top_k)

        # Also fetch issue_type matches for display
        issue_type_matches = []
        if new_info.get("issue_type"):
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (t:Ticket)-[:HAS_ISSUE_TYPE]->(i:IssueType {name: $name})
                    RETURN t.id AS id, t.summary AS summary
                    LIMIT $limit
                    """,
                    name=new_info["issue_type"],
                    limit=top_k,
                )
                issue_type_matches = [dict(r) for r in result]

        action_matches = []
        if new_info.get("action"):
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (t:Ticket)-[:HAS_ACTION]->(a:Action {name: $name})
                    RETURN t.id AS id, t.summary AS summary
                    LIMIT $limit
                    """,
                    name=new_info["action"],
                    limit=top_k,
                )
                action_matches = [dict(r) for r in result]

        return {
            "ticket_summary": new_ticket_summary,
            "extracted": new_info,
            "ranked_resolutions": ranked,
            "exact_matches": issue_type_matches,
            "action_matches": action_matches,
            "routing": self.get_routing(new_info),
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_graph_stats(self) -> Dict:
        with self.driver.session() as session:
            ticket_count = session.run(
                "MATCH (t:Ticket) RETURN count(t) AS c"
            ).single()["c"]
            issue_type_count = session.run(
                "MATCH (i:IssueType) RETURN count(i) AS c"
            ).single()["c"]
            object_count = session.run(
                "MATCH (o:SalesforceObject) RETURN count(o) AS c"
            ).single()["c"]
            action_count = session.run(
                "MATCH (a:Action) RETURN count(a) AS c"
            ).single()["c"]
            resolution_count = session.run(
                "MATCH (r:Resolution) RETURN count(r) AS c"
            ).single()["c"]
            similarity_count = session.run(
                "MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS c"
            ).single()["c"]

        return {
            "ticket_count": ticket_count,
            "issue_type_count": issue_type_count,
            "object_count": object_count,
            "action_count": action_count,
            "resolution_count": resolution_count,
            "similarity_count": similarity_count,
        }
