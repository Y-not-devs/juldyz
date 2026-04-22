# JULDYZ — EXPLAINABLE AI PLATFORM FOR CANDIDATE EVALUATION

## OVERVIEW

Juldyz is an explainable AI system designed to assist in evaluating candidates based on real growth signals, experience trajectory, and authenticity rather than purely formal application quality.

The system aggregates multiple data sources and transforms them into a structured candidate profile that supports human decision-making.

Juldyz does not replace human evaluators. It provides structured insights to reduce manual analysis effort.

---

## CORE PRINCIPLES

- Human-in-the-loop decision making
- Explainable scoring for every evaluation
- Multi-source data aggregation
- Transparency over automation

---

## SYSTEM ARCHITECTURE

juldyz/
- core/        Shared modules (config, database, logging)
- scripts/     Local execution scripts
- services/
    - bot/        Telegram-based candidate interaction service
    - dashboard/  Streamlit web interface for reviewers
    - form/       Candidate submission API
    - llm/        LLM integration layer (experimental)
    - parser/     External data extraction (GitHub, CV parsing)
    - scoring/    Explainable scoring engine
- data/        Local storage of processed artifacts

---

## IMPLEMENTED COMPONENTS

### PARSER SERVICE
- GitHub API integration for profile extraction
- Repository metadata collection
- PDF CV parsing and structured extraction
- Skills and contact information extraction
- Validation and error handling

### SCORING SERVICE
- Weighted evaluation model:
  Final Score = (A × 2.0 + B × 3.0 + C × 1.5) / 6.5
- A: Experience signals
- B: Motivation and leadership signals
- C: Authenticity and growth indicators
- Explainable output with textual justification
- Candidate categorization into performance buckets

### DATABASE
- SQLite-based persistence layer
- Stores candidate submissions, parsed data, and scoring results

### DASHBOARD
- Candidate overview interface
- Manual scoring configuration interface
- Candidate list view from database
- Grading criteria documentation

---

## INCOMPLETE / EXPERIMENTAL COMPONENTS

### LLM SERVICE
- Schema and structure defined
- No production LLM backend integrated
- No task execution system implemented

### TELEGRAM BOT
- Basic service structure exists
- Not connected to scoring pipeline
- No validated end-to-end workflow

### YOUTUBE PARSER
- Experimental implementation
- Dependency-heavy transcription pipeline
- Not integrated into scoring system

### ANTI-AI DETECTION
- Concept exists in database schema
- No working detection logic implemented

### ORCHESTRATION LAYER
- Partial implementation in main entrypoint
- Service lifecycle management incomplete
- No fully verified inter-service communication

---

## SYSTEM STATUS

Scoring Engine:          WORKING  
GitHub/PDF Parser:       WORKING  
Database:                WORKING  
Dashboard:               PARTIAL  
Telegram Bot:            INCOMPLETE
LLM Integration:         NOT IMPLEMENTED  
YouTube Analysis:        EXPERIMENTAL  
Anti-AI Detection:       NOT IMPLEMENTED  
End-to-End Pipeline:     INCOMPLETE  

Current Stage: Pre-MVP

---

## LOCAL RUN INSTRUCTIONS

1. Create virtual environment:
   python -m venv .venv

2. Activate environment:
   source .venv/bin/activate   (Linux/Mac)
   .\.venv\Scripts\activate    (Windows)

3. Install dependencies:
   pip install -r requirements.txt

4. Run system:
   PYTHONPATH=. python main.py

---

## DESIGN GOALS

- Maintain human control over final decisions
- Avoid black-box scoring systems
- Provide transparent evaluation reasoning
- Keep modular and extensible architecture