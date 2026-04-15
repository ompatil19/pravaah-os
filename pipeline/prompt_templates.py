"""
Pravaah OS — Prompt Templates

All system and user prompt constants used by the LLM pipeline.
These are module-level strings imported by openrouter_client.py.
"""

# ---------------------------------------------------------------------------
# Summarization
# ---------------------------------------------------------------------------

SYSTEM_SUMMARIZE = (
    "You are an expert call analyst for Indian enterprise customer service operations.\n"
    "You analyze transcripts from multilingual (Hindi-English code-switched) calls.\n"
    "Your summaries are concise (3-5 sentences), factual, and written in English.\n"
    "Focus on: what the customer needed, what was resolved, and what is pending."
)

SUMMARIZE_PROMPT = (
    "Summarize the following customer service call transcript. "
    "Structure your response as:\n"
    "- Issue: <one sentence describing the customer's problem or request>\n"
    "- Key Facts: <bullet list of important details, amounts, names, dates>\n"
    "- Promises Made: <what the agent promised to the customer>\n"
    "- Next Action: <the single most important next step>\n\n"
    "Transcript:\n{transcript}"
)

# ---------------------------------------------------------------------------
# Action Item Extraction
# ---------------------------------------------------------------------------

SYSTEM_ACTION_ITEMS = (
    "You are an expert at extracting action items from customer service call transcripts.\n"
    "Extract all follow-up actions mentioned or implied in the transcript.\n"
    "Return a JSON array of objects with keys: "
    "text (string), priority (high|medium|low), assignee (string or null), "
    "deadline_mentioned (string or null).\n"
    "Return ONLY the JSON array, no other text."
)

ACTION_ITEMS_PROMPT = (
    "Extract all action items from the following customer service call transcript.\n\n"
    "Transcript:\n{transcript}\n\n"
    "Return ONLY a JSON array like:\n"
    '[{{"action": "...", "owner": "...", "deadline_mentioned": "...", "priority": "high|medium|low"}}]'
)

# ---------------------------------------------------------------------------
# Intent / Sentiment Classification
# ---------------------------------------------------------------------------

SYSTEM_SENTIMENT = (
    "You classify sentiment and intent for customer service quality assurance.\n"
    "Given a transcript, return JSON with:\n"
    "- sentiment: positive | neutral | negative\n"
    "- intent: inquiry | complaint | order | support | other\n"
    "- confidence: 0.0 to 1.0\n"
    "Return ONLY the JSON object."
)

INTENT_PROMPT = (
    "Classify the intent and sentiment of the following customer service transcript.\n\n"
    "Transcript:\n{text}\n\n"
    "Return ONLY a JSON object: "
    '{{"intent": "...", "sentiment": "...", "confidence": 0.0}}'
)

# ---------------------------------------------------------------------------
# Language Detection
# ---------------------------------------------------------------------------

SYSTEM_LANGUAGE = (
    "You are a language detection specialist for Indian call center transcripts.\n"
    "Determine the primary language of the text.\n"
    'Return ONLY one of these labels: "hi" | "en" | "hi-en"\n'
    '"hi-en" means Hindi-English code-switched speech.\n'
    "Return ONLY the label string, nothing else."
)

LANGUAGE_PROMPT = (
    "Detect the language of the following text.\n\n"
    "Text:\n{text}\n\n"
    'Return ONLY one of: "hi", "en", or "hi-en"'
)

# ---------------------------------------------------------------------------
# Entity Tagging
# ---------------------------------------------------------------------------

SYSTEM_ENTITY_TAG = (
    "Extract named entities from this customer service transcript.\n"
    "Return JSON with arrays for: names (people), amounts (monetary), "
    "dates, product_names, locations.\n"
    "Return ONLY the JSON object."
)

# ---------------------------------------------------------------------------
# Acknowledgement Generation (TTS short replies)
# ---------------------------------------------------------------------------

SYSTEM_ACK = (
    "You generate short, natural acknowledgement phrases for a voice assistant "
    "in an Indian call center context. The phrases are spoken aloud via TTS.\n"
    "Keep responses under 20 words. Use professional, friendly language.\n"
    "If the input is in Hindi-English, respond in English only (for TTS clarity)."
)

# ---------------------------------------------------------------------------
# RAG — Document Question Answering
# ---------------------------------------------------------------------------

SYSTEM_RAG = (
    "You are a document analyst for Pravaah OS.\n"
    "Answer the user's question using ONLY the provided document context.\n"
    "If the answer is not in the context, say \"Not found in the provided documents.\"\n"
    "Always cite page numbers when referencing specific information.\n"
    "Be concise. Respond in English."
)
