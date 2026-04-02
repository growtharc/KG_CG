# KG_CG Project Presentation

## Overview
The KG_CG project demonstrates a dual-graph architecture using Neo4j for managing structured ticket data (Knowledge Graph) and unstructured contextual information (Context Graph). This system enables intelligent ticket routing, similarity analysis, and context-aware data ingestion from various sources like PDFs.

## Role of Knowledge Graph (KG)
The Knowledge Graph serves as the core structured data layer for ticket management and analysis:
- **Nodes**: Ticket (with summaries), Action, Object, Problem
- **Relationships**: HAS_ACTION, HAS_OBJECT, HAS_PROBLEM, SIMILAR_TO
- **Purpose**: 
  - Store and organize ticket data from sources like Jira
  - Enable similarity-based ticket routing and recommendations
  - Support exact and action-based matching for new tickets
  - Provide statistical insights on ticket patterns

## Role of Context Graph (CG)
The Context Graph acts as an intermediate layer for processing unstructured data:
- **Nodes**: ContextDocument, ContextPage, ContextChunk, ContextAction, ContextObject, ContextProblem
- **Relationships**: HAS_PAGE, HAS_CHUNK, MENTIONS_ACTION/OBJECT/PROBLEM
- **Purpose**:
  - Ingest and chunk unstructured text from PDFs or manual input
  - Extract structured information (action, object, problem) from raw text
  - Provide a review layer before promoting data to the Knowledge Graph
  - Maintain document provenance and chunk-level granularity

## Streamlit App Functionalities

### Data Setup and KG Management
- **Load Sample Tickets**: Import ticket data from CSV files into the Knowledge Graph
- **Graph Statistics**: Display metrics for tickets, actions, objects, and similarity links
- **Similarity Link Creation**: Automatically generate SIMILAR_TO relationships based on shared actions and objects

### Context Graph Builder
- **Manual Context Creation**: Add individual text chunks with extracted entities
- **PDF Ingestion**: Upload PDF files, automatically parse into chunks, and build context graph
- **Context Statistics**: Track documents, pages, chunks, and extracted entities
- **Clear Context Graph**: Reset the context layer for fresh ingestion

### Ticket Analysis and Routing
- **Similar Ticket Search**: Find exact matches (same action+object) and action-based matches
- **Entity Extraction**: Automatically identify action, object, and problem from ticket summaries
- **Routing Suggestions**: Provide intelligent routing recommendations based on extracted information

### Advanced Features
- **Context-to-KG Trace**: Demonstrate how extracted context creates KG nodes and relationships
- **Cypher Query Panel**: Execute custom Neo4j queries for ad-hoc analysis
- **Real-time Metrics**: Live updates of graph statistics and processing results

## Future Enhancements: Memory-Based File Management

### Current Limitation
The system currently processes uploaded files (PDFs) in-memory or temporary storage, losing the original files after processing. This limits auditability and reprocessing capabilities.

### Proposed Memory Integration
Implement a persistent memory system to:
- **Store Uploaded Files**: Save user-uploaded PDFs in a dedicated memory store with metadata
- **Track Processing History**: Maintain records of extraction results, timestamps, and user approvals
- **Enable Reprocessing**: Allow users to re-run extractions on stored files with different parameters
- **Support Incremental Updates**: Compare new uploads against existing memory to avoid duplicate processing
- **Provide File Management UI**: Add interface for browsing, downloading, and managing stored files

### Technical Implementation
- Use vector embeddings for file content similarity detection
- Implement file versioning and change tracking
- Add user permission controls for file access
- Integrate with existing graph structure for file-entity relationships

### Benefits
- Improved audit trail for data ingestion processes
- Reduced processing overhead through intelligent caching
- Enhanced user experience with file history and management
- Foundation for advanced features like file-based recommendations

## Conclusion
The KG_CG project showcases a robust approach to combining structured and unstructured data processing using graph databases. The dual-graph architecture provides flexibility for data ingestion while maintaining data quality through the review layer. Future memory integration will enhance the system's capabilities for enterprise-scale document processing and analysis.</content>
<parameter name="filePath">c:\Users\RadhikaAgarwal\Downloads\KG_CG\KG_CG\PRESENTATION.md