# Zecpath ATS — Architecture Diagrams

**Day 19 deliverable | Version 1.0**

These diagrams describe the repository's current logical architecture. They are not deployment diagrams for a production microservices environment.

## 1. System context

```mermaid
flowchart LR
    Recruiter[Recruiter / Internal Client]
    Candidate[Candidate Resume File]
    API[Zecpath FastAPI Application]
    ATS[ATS Processing Modules]
    Results[Task Results / Rankings]
    Recruiter -->|REST requests| API
    Candidate -->|PDF / DOCX upload| API
    API --> ATS
    ATS --> Results
    Results -->|JSON responses| Recruiter
```

## 2. Component architecture

```mermaid
flowchart TB
    subgraph Interface["API / Orchestration"]
      FastAPI["api/main.py<br/>FastAPI routes + adapters"]
      Tasks["In-memory task registry"]
      Uploads["Local upload directory"]
    end

    subgraph Parsing["Parsing and normalization"]
      Extract["resume_extractor"]
      Segment["resume_section_classifier"]
      Skills["skill_ner"]
      Experience["experience_parser"]
      Education["education_certification_parser"]
      JD["jd_parser"]
    end

    subgraph Intelligence["Matching and decision support"]
      SkillMatch["ats_engine.matcher"]
      Semantic["semantic_matching_engine"]
      ExpRel["experience_relevance_engine"]
      EduRel["education_relevance_engine"]
      Scoring["scoring.ats_scoring_engine"]
      Ranking["ranking.candidate_ranking_engine"]
      Shortlist["shortlisting.shortlisting_engine"]
    end

    subgraph Governance["Fairness and evaluation"]
      Fairness["fairness package"]
      Tests["tests / reports"]
    end

    FastAPI --> Tasks
    FastAPI --> Uploads
    Uploads --> Extract
    Extract --> Segment
    Segment --> Skills
    Segment --> Experience
    Segment --> Education
    JD --> SkillMatch
    Skills --> SkillMatch
    Skills --> Semantic
    Experience --> ExpRel
    Education --> EduRel
    SkillMatch --> Scoring
    Semantic --> Scoring
    ExpRel --> Scoring
    EduRel --> Scoring
    Scoring --> Ranking
    Scoring --> Shortlist
    Fairness -. supporting audit .-> Scoring
    Tests -. verify .-> Parsing
    Tests -. verify .-> Intelligence
```

## 3. Resume processing data flow

```mermaid
flowchart TD
    A[PDF / DOCX] --> B[Upload validation]
    B --> C[Local file write]
    C --> D[Resume extraction]
    D --> E[Text cleanup / OCR fallback if configured]
    E --> F[Section classification]
    F --> G[Skills extraction]
    F --> H[Experience extraction]
    F --> I[Education / certification extraction]
    G --> J[Structured resume profile]
    H --> J
    I --> J
    J --> K[Resume schema contract]
    K --> L[Downstream matching and scoring]
```

## 4. Scoring and ranking flow

```mermaid
flowchart TD
    A[Candidate profile + job requirements] --> B[Skill match score]
    A --> C[Experience relevance score]
    A --> D[Education alignment score]
    A --> E[Semantic similarity score]
    B --> F[Validate component values 0–100]
    C --> F
    D --> F
    E --> F
    F --> G[Select default or role-specific weights]
    G --> H{Any valid component scores?}
    H -->|No| I[overall_score = null<br/>insufficient_data]
    H -->|Yes| J[Renormalize available weights]
    J --> K[Weighted overall score + explanation]
    K --> L[Candidate ranking]
    K --> M[Shortlisting classification]
    I --> N[Manual review]
    M --> N
```

## 5. API request lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Store as In-memory registries
    participant Worker as asyncio task
    participant Engine as ATS module

    Client->>API: POST upload / score / shortlist
    API->>Store: Create record and task ID
    API->>Worker: Schedule async operation
    API-->>Client: 202 Accepted + task_id
    Worker->>Engine: Execute adapter
    Engine-->>Worker: Result
    Worker->>Store: Save task result/status
    Client->>API: GET /api/v1/tasks/{task_id}
    API->>Store: Read task
    API-->>Client: Current status/result
```

**Important limitation:** The task registry and related API state are in memory. This sequence does not provide durable execution, cross-process coordination, or recovery after a restart.
