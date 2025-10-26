# 📌 LogBuster — Intelligent Log Analysis & Insight Engine

LogBuster is an interactive log-analysis desktop tool built using **Python + PySide6**, with a hybrid approach of **Rule-based parsing** and **LLM-based insights**. It is designed for engineers who frequently debug complex backend systems, pipelines, chatbots, or microservices by searching, extracting, and understanding patterns buried inside large log files.

---

## 🚀 Key Features

| Feature | Description |
|---------|------------|
| **Fast search & filtering** | Rule-based search across nested folders, including JSON logs |
| **Schema-driven extraction** | Register log structures and extract only the meaningful fields |
| **Parser auto-generation** | Automatically generates parser classes for each schema |
| **AI Insight Mode (LLM)** | Summarizes logs, detects anomalies, and finds root causes |
| **Map-Reduce AI Summaries** | Handles large logs by chunking + combining insights |
| **Exportable Results** | Export extracted logs and AI insights to Text/JSON/Markdown |

---

## 🧠 Why Hybrid (Rule-Based + AI)?

Logs contain **high-variance keys, repeating structures, arrays, timestamps, and noise**. We learned early that:

| Task Type | Best Solution | Why |
|------------|--------------|-----|
| Schema detection, field extraction, search | ✅ **Rule-based** | Deterministic, 100% accurate, zero hallucinations |
| Explaining logs, finding patterns, RCA | ✅ **LLM (AI)** | AI is ideal for *reasoning*, not parsing |
| Matching unknown field names | ✅ **Rule-based normalization** | Developers may use different suffixes or formats |
| Merging similar arrays | ✅ **Rule-based superset logic** | Ensures consistent schemas even when fields differ |

This balance gives us **reliability + intelligence** instead of AI chaos or brittle regex-only parsing.

---

## 📌 Workflow

```
1) User loads personal JSON logs
2) Registers schema (AI-assisted structural extraction)
3) Searches / extracts chosen fields → clean dataset
4) (Optional) Clicks “Generate AI Insight”
5) AI produces:
   - Summary
   - Timeline
   - Anomalies
   - Root Cause
   - Suggestions
```

---

## ✅ Example Use Cases

- LLM chatbot pipeline debugging  
- Customer support session logs  
- Microservice request flow tracing  
- Intent/subquery tracing in AI pipelines  
- Root-cause analysis for failed responses  

---

## 🏗️ Tech Stack

| Component | Tech |
|-----------|------|
| UI | PySide6 |
| Backend | Python 3.10+ |
| AI | Ollama (Llama3) |
| Threading | QThread (non-blocking UI) |
| Parsing | Rule-based JSON walker |

---

## 📌 AI Insight Strategy (Map-Reduce)

If the extracted file fits inside model context → **Single LLM call**  
If large → **Chunk → Summarize → Merge summaries → Final synthesis**

This enables AI reasoning **without token overflow**.

---

## 📦 Project Status

| Module | Status |
|---------|--------|
| Extraction | ✅ Complete |
| Schema Registration | ✅ Complete |
| AI Insight Mode | ✅ Complete |
| Export Insight | ✅ Complete |
| Packaging / EXE | ❌ (Not needed now) |

---

## 🧪 Sample Logs

We provide 3 test logs in `samples/` to validate:
- Successful flow
- Retrieval failure
- Slow multi-step reasoning flow

---

## 🎯 Future Enhancements (optional)

- Compare insights across N logs
- Trend detection
- Alert scoring
- Slack/Jira integration

---

## 🤝 Contributions
PRs welcome. Ideas welcome. Criticism welcome.

---

## 📌 Author
**Justin M.** — (LogBuster — 2025)

