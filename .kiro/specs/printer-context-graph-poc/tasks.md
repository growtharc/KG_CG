# Implementation Plan: Printer Context Graph POC

## Overview

Refactor the existing Neo4j ticket context graph demo to use a richer, domain-specific schema for Salesforce/Jira printer-support tickets. Changes span entity extraction, KG schema, context graph schema, scoring engine, stats keys, and UI labels.

## Tasks

- [x] 1. Rewrite `backend/common.py` — new `extract_info()` and `get_routing()`
  - [x] 1.1 Rewrite `extract_info()` to return `{action, object, issue_type, resolution}` using expanded keyword rules
    - Replace the existing `problem` field with `issue_type` and add `resolution`
    - Implement priority-ordered keyword matching per the design rules (DELETE/REMOVE → "DELETE", MERGE/DEDUPLICATE → "MERGE", ACCESS/PERMISSION → "ACCESS", REASSIGN/TRANSFER → "REASSIGN", CREATE/ADD → "CREATE", UPDATE/EDIT/MOVE → "UPDATE")
    - Implement object keywords: OPPORTUNITY/OPP → "Opportunity", ACCOUNT → "Account", CASE → "Case", LEAD → "Lead", CONTACT → "Contact", ONBOARDING → "Onboarding", REPORT → "Report"
    - Implement issue_type keywords: DUPLICATE → "Duplicate", PERMISSION/ACCESS → "Permission", DATA QUALITY/CORRUPT → "DataQuality", INTEGRATION/SYNC → "Integration", MISSING/NOT FOUND → "MissingData"
    - Implement resolution keywords: MERGE/MERGED → "MergeRecords", GRANT/GRANTED → "GrantAccess", DELETE/DELETED → "DeleteRecord", REASSIGN/REASSIGNED → "ReassignRecord", SYNC/SYNCED → "TriggerSync", ESCALAT → "Escalate"
    - _Requirements: R1.1, R1.2_
  - [x] 1.2 Rewrite `get_routing()` to branch on `info["issue_type"]` and `info["action"]` (remove `problem` references)
    - Duplicate → "Data Quality Team", Permission → "Salesforce Admin Team", Integration → "Integration Team", DELETE/MERGE action → "Data Operations Team", CREATE → "Data Operations Team", else → "General Support Queue"
    - _Requirements: R1.3_

- [x] 2. Rewrite `backend/kg_service.py` — new schema, hardcoded dataset, scoring engine
  - [x] 2.1 Add `HARDCODED_TICKETS` class constant (10 tickets with `id`, `summary`, `resolution`)
    - Use the exact 10-ticket dataset from the design document
    - _Requirements: R2.1_
  - [x] 2.2 Implement `ensure_kg_schema()` — create Neo4j uniqueness constraints for Ticket, IssueType, SalesforceObject, Action, Resolution
    - _Requirements: R2.2_
  - [x] 2.3 Rewrite `add_ticket(ticket_id, summary, resolution=None)` to use new node labels and relationships
    - Call `extract_info()` to get `{action, object, issue_type, resolution}`
    - Create `Ticket` node; MERGE `IssueType`, `SalesforceObject`, `Action`, `Resolution` nodes
    - Create relationships: `HAS_ISSUE_TYPE`, `INVOLVES_OBJECT`, `HAS_ACTION`, `RESOLVED_BY`
    - Use `resolution` param if provided, else fall back to `extract_info()` result
    - _Requirements: R2.2, R2.3_
  - [x] 2.4 Implement `load_hardcoded_tickets()` — replaces `load_sample_tickets()` CSV path
    - Call `clear_all()`, iterate `HARDCODED_TICKETS`, call `add_ticket()` for each, then `create_similarity_links()`
    - _Requirements: R2.1_
  - [x] 2.5 Rewrite `create_similarity_links()` to match on shared `IssueType` + `SalesforceObject` (not Action + Object)
    - Create `SIMILAR_TO` edges; also create `TYPICALLY_INVOLVES` (IssueType → SalesforceObject) and `TYPICALLY_RESOLVES_WITH` (IssueType → Resolution) statistical edges
    - _Requirements: R2.4_
  - [ ]* 2.6 Write property test for `add_ticket` → issue_type round-trip (Property 2)
    - **Property 2: Ticket add → issue_type query round-trip**
    - **Validates: Requirements R2.2, R4.2**
  - [x] 2.7 Implement `score_and_rank(summary, top_k=3)` scoring engine
    - Fetch all stored tickets from Neo4j with `summary`, `issue_type`, `object`, `action`, `resolution`
    - Extract info from query summary using `extract_info()`
    - Fit `TfidfVectorizer` over stored summaries; compute cosine similarity; identify TF-IDF top-3
    - Apply weighted scoring per ticket: issue_type match +4, object match +3, action match +3, in TF-IDF top-3 +5, resolution appears ≥2 times across all tickets +2
    - Group by resolution, sum scores; return top-k sorted descending with `resolution`, `score`, `supporting_tickets`, `explanation`
    - Guard: if no stored tickets, skip TF-IDF and return empty list
    - _Requirements: R5.1, R5.2, R5.3_
  - [ ]* 2.8 Write property test for scoring weights (Property 3)
    - **Property 3: Scoring weights are respected — issue_type match contributes ≥4, object match ≥3, action match ≥3**
    - **Validates: Requirements R5.1, R5.2**
  - [ ]* 2.9 Write property test for top-ranked resolution (Property 4)
    - **Property 4: Top-ranked resolution matches known resolution for each hardcoded ticket**
    - **Validates: Requirements R5.3**
  - [x] 2.10 Rewrite `get_graph_stats()` to return 6 keys: `ticket_count`, `issue_type_count`, `object_count`, `action_count`, `resolution_count`, `similarity_count`
    - Remove `problem_count`; query `IssueType` and `Resolution` node counts
    - _Requirements: R6.1_
  - [ ]* 2.11 Write property test for KG stats keys and values (Property 5)
    - **Property 5: `get_graph_stats()` returns all 6 required keys with non-negative integer values**
    - **Validates: Requirements R6.1**

- [x] 3. Checkpoint — ensure KG service tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Rewrite `backend/context_service.py` — new context node/relationship types
  - [x] 4.1 Rewrite `ensure_context_graph_schema()` to create constraints for `ContextIssueType`, `ContextSalesforceObject`, `ContextResolution` (remove `ContextAction`, `ContextObject`, `ContextProblem`)
    - _Requirements: R3.1_
  - [x] 4.2 Rewrite `clear_context_graph()` to delete `ContextIssueType`, `ContextSalesforceObject`, `ContextResolution` nodes (remove old labels)
    - _Requirements: R3.1_
  - [x] 4.3 Rewrite `create_context_graph_from_summary()` to use new node labels and relationships
    - Replace `ContextAction`/`MENTIONS_ACTION` with `ContextIssueType`/`MENTIONS_ISSUE_TYPE`
    - Replace `ContextObject`/`MENTIONS_OBJECT` with `ContextSalesforceObject`/`MENTIONS_OBJECT`
    - Replace `ContextProblem`/`MENTIONS_PROBLEM` with `ContextResolution`/`MENTIONS_RESOLUTION`
    - Use `extracted["issue_type"]` for `ContextIssueType`, `extracted["object"]` for `ContextSalesforceObject`, `extracted["resolution"]` for `ContextResolution`
    - _Requirements: R3.2_
  - [ ]* 4.4 Write property test for context chunk → MENTIONS_ISSUE_TYPE round-trip (Property 7)
    - **Property 7: After `create_context_graph_from_summary()`, querying MENTIONS_ISSUE_TYPE returns the created chunk**
    - **Validates: Requirements R3.2**
  - [x] 4.5 Rewrite `get_context_graph_stats()` to return 6 keys: `document_count`, `page_count`, `chunk_count`, `issue_type_count`, `object_count`, `resolution_count`
    - Remove `action_count` and `problem_count`; query `ContextIssueType` and `ContextResolution` node counts
    - _Requirements: R6.2_
  - [ ]* 4.6 Write property test for context graph stats keys and values (Property 6)
    - **Property 6: `get_context_graph_stats()` returns all 6 required keys with non-negative integer values**
    - **Validates: Requirements R6.2**

- [x] 5. Update `main.py` — pass-through updates for new method signatures
  - [x] 5.1 Replace `load_sample_tickets()` facade with `load_hardcoded_tickets()` delegating to `self.kg.load_hardcoded_tickets()`
    - _Requirements: R2.1_
  - [x] 5.2 Add `score_and_rank(summary, top_k=3)` facade method delegating to `self.kg.score_and_rank()`
    - _Requirements: R5.1_
  - [x] 5.3 Update `show_graph_stats()` print statements to use `issue_type_count` and `resolution_count` instead of `problem_count`
    - _Requirements: R6.1_
  - [x] 5.4 Update `find_similar_tickets()` to print `issue_type` and `resolution` instead of `problem`
    - _Requirements: R1.1_

- [x] 6. Update `ui/streamlit_app.py` — metric label and result display updates
  - [x] 6.1 Rewrite `render_stats()` to use 6 columns with labels: Tickets, Issue Types, Resolutions, Objects, Actions, Similarity Links — using new stat keys
    - _Requirements: R6.1_
  - [x] 6.2 Rewrite `render_context_stats()` metric labels to: Context Documents, Context Pages, Context Chunks, Context Issue Types, Context Objects, Context Resolutions — using new stat keys
    - _Requirements: R6.2_
  - [x] 6.3 Update the sidebar "Load Sample Tickets" button to call `load_hardcoded_tickets()` instead of `load_sample_tickets()` (remove CSV path / limit inputs)
    - _Requirements: R2.1_
  - [x] 6.4 Update "Find Similar Tickets" result panel to call `score_and_rank()` and display ranked resolutions with `issue_type`/`resolution` instead of `problem`
    - Show each ranked result's `resolution`, `score`, `supporting_tickets`, and `explanation`
    - _Requirements: R5.3_
  - [x] 6.5 Update "Context -> KG Trace" panel to display `issue_type` and `resolution` instead of `problem` in extracted info columns
    - _Requirements: R1.1_
  - [x] 6.6 Update PDF sample traces dataframe to show `issue_type` and `resolution` columns instead of `problem`
    - _Requirements: R1.1_

- [ ] 7. Write property-based tests in `tests/test_properties.py`
  - [ ]* 7.1 Write property test for `extract_info` on all hardcoded tickets (Property 1)
    - **Property 1: `extract_info()` returns non-None `action` and `issue_type` for all hardcoded tickets**
    - Use `@given(ticket=st.sampled_from(KnowledgeGraphService.HARDCODED_TICKETS))`, `@settings(max_examples=100)`
    - Assert `result["action"] is not None` and `result["issue_type"] is not None`
    - Tag: `# Feature: printer-context-graph-poc, Property 1: extract_info returns non-None action and issue_type for all hardcoded tickets`
    - **Validates: Requirements R1.1, R1.2**
  - [ ]* 7.2 Write property test for ticket add → issue_type round-trip (Property 2)
    - **Property 2: After `add_ticket()`, querying IssueType-linked tickets includes the added ticket ID**
    - Use `@given(ticket=st.sampled_from(KnowledgeGraphService.HARDCODED_TICKETS))`, `@settings(max_examples=100)`
    - Tag: `# Feature: printer-context-graph-poc, Property 2: ticket add → issue_type query round-trip`
    - **Validates: Requirements R2.2, R4.2**
  - [ ]* 7.3 Write property test for scoring weights (Property 3)
    - **Property 3: issue_type match contributes ≥4 points, object match ≥3, action match ≥3**
    - Use `@given(ticket=st.sampled_from(KnowledgeGraphService.HARDCODED_TICKETS))`, `@settings(max_examples=100)`
    - Tag: `# Feature: printer-context-graph-poc, Property 3: scoring weights are respected`
    - **Validates: Requirements R5.1, R5.2**
  - [ ]* 7.4 Write property test for top-ranked resolution (Property 4)
    - **Property 4: `score_and_rank(summary)` top result's `resolution` equals the ticket's known resolution**
    - Use `@given(ticket=st.sampled_from(KnowledgeGraphService.HARDCODED_TICKETS))`, `@settings(max_examples=100)`
    - Tag: `# Feature: printer-context-graph-poc, Property 4: top-ranked resolution matches known resolution`
    - **Validates: Requirements R5.3**
  - [ ]* 7.5 Write property test for KG stats keys and values (Property 5)
    - **Property 5: `get_graph_stats()` returns exactly 6 required keys, all non-negative integers**
    - Use `@given(st.just(None))`, `@settings(max_examples=100)`, fixed setup with `load_hardcoded_tickets()`
    - Tag: `# Feature: printer-context-graph-poc, Property 5: KG stats dict has all required keys and non-negative values`
    - **Validates: Requirements R6.1**
  - [ ]* 7.6 Write property test for context graph stats keys and values (Property 6)
    - **Property 6: `get_context_graph_stats()` returns exactly 6 required keys, all non-negative integers**
    - Use `@given(summary=st.text(min_size=5))`, `@settings(max_examples=100)`
    - Tag: `# Feature: printer-context-graph-poc, Property 6: context graph stats dict has all required keys and non-negative values`
    - **Validates: Requirements R6.2**
  - [ ]* 7.7 Write property test for context chunk → MENTIONS_ISSUE_TYPE round-trip (Property 7)
    - **Property 7: After `create_context_graph_from_summary()`, MENTIONS_ISSUE_TYPE query returns the created chunk**
    - Use `@given(ticket=st.sampled_from(KnowledgeGraphService.HARDCODED_TICKETS))` filtered to tickets with non-None issue_type, `@settings(max_examples=100)`
    - Tag: `# Feature: printer-context-graph-poc, Property 7: context chunk round-trip — MENTIONS_ISSUE_TYPE relationship`
    - **Validates: Requirements R3.2**

- [-] 8. Final checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All property tests use Hypothesis with `max_examples=100`
- Properties 2, 4, 6, 7 require a live Neo4j connection; use a test database or mock driver
- `score_and_rank()` replaces `query_similar_tickets()` as the primary similarity API
- The CSV-based `load_sample_tickets()` is fully replaced by `load_hardcoded_tickets()`
