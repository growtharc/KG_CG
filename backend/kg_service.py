from datetime import datetime
from typing import Callable, Dict, List

import pandas as pd


class KnowledgeGraphService:
    def __init__(
        self,
        driver,
        extract_info_fn: Callable[[str], Dict],
        get_routing_fn: Callable[[Dict], str],
    ):
        self.driver = driver
        self.extract_info = extract_info_fn
        self.get_routing = get_routing_fn

    def clear_all(self):
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def add_ticket(self, ticket_id: str, summary: str):
        info = self.extract_info(summary)
        with self.driver.session() as session:
            session.run(
                """
                CREATE (t:Ticket {
                    id: $id,
                    summary: $summary
                })
                """,
                id=ticket_id,
                summary=summary,
            )
            if info["action"]:
                session.run(
                    """
                    MATCH (t:Ticket {id: $ticket_id})
                    MERGE (a:Action {name: $action})
                    CREATE (t)-[:HAS_ACTION]->(a)
                    """,
                    ticket_id=ticket_id,
                    action=info["action"],
                )
            if info["object"]:
                session.run(
                    """
                    MATCH (t:Ticket {id: $ticket_id})
                    MERGE (o:Object {name: $object})
                    CREATE (t)-[:HAS_OBJECT]->(o)
                    """,
                    ticket_id=ticket_id,
                    object=info["object"],
                )
            if info["problem"]:
                session.run(
                    """
                    MATCH (t:Ticket {id: $ticket_id})
                    MERGE (p:Problem {name: $problem})
                    CREATE (t)-[:HAS_PROBLEM]->(p)
                    """,
                    ticket_id=ticket_id,
                    problem=info["problem"],
                )

    def add_ticket_with_trace(self, summary: str, ticket_id: str = "") -> Dict:
        final_ticket_id = ticket_id.strip() or f"DEMO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        extracted = self.extract_info(summary)
        self.add_ticket(final_ticket_id, summary)

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Ticket {id: $ticket_id})
                OPTIONAL MATCH (t)-[r]->(x)
                RETURN t.id AS ticket_id,
                       t.summary AS ticket_summary,
                       type(r) AS relationship,
                       labels(x) AS target_labels,
                       x.name AS target_name
                ORDER BY relationship
                """,
                ticket_id=final_ticket_id,
            )
            rows = [dict(record) for record in result]

        return {
            "ticket_id": final_ticket_id,
            "summary": summary,
            "extracted": extracted,
            "routing": self.get_routing(extracted),
            "write_cypher": [
                "CREATE (t:Ticket {id: $id, summary: $summary})",
                "MATCH (t:Ticket {id: $ticket_id}) MERGE (a:Action {name: $action}) CREATE (t)-[:HAS_ACTION]->(a)",
                "MATCH (t:Ticket {id: $ticket_id}) MERGE (o:Object {name: $object}) CREATE (t)-[:HAS_OBJECT]->(o)",
                "MATCH (t:Ticket {id: $ticket_id}) MERGE (p:Problem {name: $problem}) CREATE (t)-[:HAS_PROBLEM]->(p)",
            ],
            "created_links": rows,
        }

    def create_similarity_links(self):
        with self.driver.session() as session:
            session.run(
                """
                MATCH (t1:Ticket)-[:HAS_ACTION]->(a:Action)<-[:HAS_ACTION]-(t2:Ticket)
                MATCH (t1)-[:HAS_OBJECT]->(o:Object)<-[:HAS_OBJECT]-(t2)
                WHERE t1.id < t2.id
                CREATE (t1)-[:SIMILAR_TO {reason: 'Same Action + Object'}]->(t2)
                """
            )

    def load_sample_tickets(
        self,
        csv_path: str = "Jira last 6 months.csv",
        limit: int = 10,
        clear_existing: bool = True,
    ) -> int:
        if clear_existing:
            self.clear_all()
        df = pd.read_csv(csv_path)
        sample_tickets = df.head(limit)
        for _, row in sample_tickets.iterrows():
            self.add_ticket(str(row["Issue key"]), str(row["Summary"]))
        self.create_similarity_links()
        return len(sample_tickets)

    def _query_exact_matches(self, action: str, obj: str, limit: int) -> List[Dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Ticket)-[:HAS_ACTION]->(a:Action {name: $action})
                MATCH (t)-[:HAS_OBJECT]->(o:Object {name: $object})
                RETURN t.id AS id, t.summary AS summary
                LIMIT $limit
                """,
                action=action,
                object=obj,
                limit=limit,
            )
            return [dict(record) for record in result]

    def _query_action_matches(self, action: str, limit: int) -> List[Dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Ticket)-[:HAS_ACTION]->(a:Action {name: $action})
                RETURN t.id AS id, t.summary AS summary, count(*) AS relevance
                ORDER BY relevance DESC
                LIMIT $limit
                """,
                action=action,
                limit=limit,
            )
            return [dict(record) for record in result]

    def query_similar_tickets(self, new_ticket_summary: str, top_k: int = 3) -> Dict:
        new_info = self.extract_info(new_ticket_summary)
        exact_matches = []
        action_matches = []

        if new_info["action"] and new_info["object"]:
            exact_matches = self._query_exact_matches(
                new_info["action"], new_info["object"], top_k
            )
        if new_info["action"]:
            action_matches = self._query_action_matches(new_info["action"], top_k)

        return {
            "ticket_summary": new_ticket_summary,
            "extracted": new_info,
            "exact_matches": exact_matches,
            "action_matches": action_matches,
            "routing": self.get_routing(new_info),
        }

    def get_graph_stats(self) -> Dict:
        with self.driver.session() as session:
            ticket_count = session.run(
                "MATCH (t:Ticket) RETURN count(t) AS ticket_count"
            ).single()["ticket_count"]
            action_count = session.run(
                "MATCH (a:Action) RETURN count(a) AS action_count"
            ).single()["action_count"]
            object_count = session.run(
                "MATCH (o:Object) RETURN count(o) AS object_count"
            ).single()["object_count"]
            similarity_count = session.run(
                "MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS similarity_count"
            ).single()["similarity_count"]

        return {
            "ticket_count": ticket_count,
            "action_count": action_count,
            "object_count": object_count,
            "similarity_count": similarity_count,
        }
