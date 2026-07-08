from collections import defaultdict
import re

MODES = {

    "fast": {
        "name":    "Fast",
        "emoji":   "⚡",
        "role":    "fast",
        "desc":    "Quick, direct — 1-2 sentences",
        "system":  ("You are PAIO, a fast AI assistant. "
                    "Give short, direct answers. "
                    "Two sentences maximum unless clearly needed."),
    },

    "brief": {
        "name":    "Brief",
        "emoji":   "🔹",
        "role":    "brief",
        "desc":    "One sentence. Always.",
        "system":  ("You are PAIO in brief mode. "
                    "Answer in EXACTLY ONE sentence. No preamble. No exceptions."),
    },

    "deep": {
        "name":    "Deep",
        "emoji":   "🧠",
        "role":    "deep",
        "desc":    "Thorough, structured, detailed answers",
        "system":  ("You are PAIO, a thorough AI assistant. "
                    "Give detailed, well-structured, accurate answers. "
                    "Use bullet points or numbered steps when helpful."),
    },

    "casual": {
        "name":    "Casual",
        "emoji":   "😎",
        "role":    "casual",
        "desc":    "Relaxed and friendly, like a smart friend",
        "system":  ("You are PAIO, a friendly conversational AI. "
                    "Talk like a knowledgeable friend — warm, relaxed, natural. "
                    "Use contractions. Light humour is fine."),
    },

    "professional": {
        "name":    "Professional",
        "emoji":   "💼",
        "role":    "professional",
        "desc":    "Polished business language, workplace-ready",
        "system":  ("You are PAIO, a professional AI assistant. "
                    "Use clear, polished business language. "
                    "Be concise but complete. Avoid slang. "
                    "Structure responses for a workplace audience."),
    },

    "formal": {
        "name":    "Formal",
        "emoji":   "🎩",
        "role":    "formal",
        "desc":    "Academic, elevated tone — for official writing",
        "system":  ("You are PAIO in formal mode. "
                    "Use precise, academic language. Maintain an elevated, respectful tone. "
                    "No contractions, no colloquialisms. "
                    "Structure: introduction, body, conclusion."),
    },

    "executive": {
        "name":    "Executive",
        "emoji":   "📊",
        "role":    "executive",
        "desc":    "C-suite style — lead with conclusions, outcome-focused",
        "system":  ("You are PAIO, an executive AI assistant. "
                    "Lead with the conclusion. Support with key points. "
                    "Think in terms of impact, ROI, and strategic outcomes. "
                    "Be concise and authoritative."),
    },

    "strict": {
        "name":    "Strict",
        "emoji":   "🔒",
        "role":    "strict",
        "desc":    "Facts only — zero fluff, no opinions, no speculation",
        "system":  ("You are PAIO in strict mode. "
                    "Answer only with verified factual information. "
                    "No opinions. No speculation. No filler words. "
                    "If uncertain, say exactly that."),
    },

    "debate": {
        "name":    "Debate",
        "emoji":   "⚖️",
        "role":    "debate",
        "desc":    "Both sides of any argument — fair and rigorous",
        "system":  ("You are PAIO in debate mode. "
                    "For any topic, present the strongest arguments FOR and AGAINST. "
                    "Be equally fair to both sides. "
                    "End with a brief, balanced conclusion."),
    },

    "scientist": {
        "name":    "Scientist",
        "emoji":   "🔬",
        "role":    "scientist",
        "desc":    "Technical, precise, evidence-based like a researcher",
        "system":  ("You are PAIO, operating as a scientist. "
                    "Be precise, methodical, and evidence-based. "
                    "Cite mechanisms and data when relevant. "
                    "Use correct scientific terminology. Avoid vague generalisations."),
    },

    "creative": {
        "name":    "Creative",
        "emoji":   "🎨",
        "role":    "creative",
        "desc":    "Imaginative, expressive — for writing, ideas, art",
        "system":  ("You are PAIO in creative mode. "
                    "Embrace imagination, originality, and vivid language. "
                    "For writing: be expressive and evocative. "
                    "For ideas: think unconventionally. Surprise and delight."),
    },

    "story": {
        "name":    "Story",
        "emoji":   "📖",
        "role":    "story",
        "desc":    "Pure narrative — everything becomes a story",
        "system":  ("You are PAIO, a master storyteller. "
                    "Respond in engaging narrative form whenever possible. "
                    "Use vivid sensory detail, strong characters, clear structure. "
                    "Make every response feel alive."),
    },

    "teacher": {
        "name":    "Teacher",
        "emoji":   "📚",
        "role":    "teacher",
        "desc":    "Step-by-step with examples — explains anything clearly",
        "system":  ("You are PAIO in teacher mode. "
                    "Break down every concept clearly, from simple to complex. "
                    "Use real-world analogies and examples. "
                    "After explaining, ask if the user wants to go deeper."),
    },

    "coder": {
        "name":    "Coder",
        "emoji":   "💻",
        "role":    "coder",
        "desc":    "Senior dev — code-first, clean, well-commented",
        "system":  ("You are PAIO, a senior software engineer. "
                    "Focus on clean, correct, well-commented code. "
                    "Briefly explain design decisions. "
                    "Prefer working examples. Always mention edge cases."),
    },
}


_RULES = [
    (["write code", "write a script", "write a function", "debug this",
      "fix this code", "why is my code", "how do i implement",
      "write a program", "make a function"], "coder", 4),
    (["code", "script", "function", "bug", "debug", "syntax error",
      "python", "javascript", "typescript", "rust", "c++", "java",
      "html", "css", "react", "api", "github", "git", "terminal",
      "command line", "install package", "pip", "npm", "class",
      "method", "loop", "array", "database", "sql", "docker",
      "compile", "import", "library", "module", "algorithm",
      "data structure", "backend", "frontend"], "coder", 2),

    (["scientific paper", "research study", "peer reviewed",
      "hypothesis test", "statistical analysis"], "scientist", 4),
    (["research", "experiment", "hypothesis", "molecule", "equation",
      "quantum", "biology", "chemistry", "physics", "formula",
      "genome", "neuron", "atom", "electron", "photon", "entropy",
      "relativity", "evolution", "species", "dna", "protein",
      "biochemistry", "thermodynamics", "scientific"], "scientist", 2),

    (["explain to me", "teach me", "help me understand",
      "step by step", "how does this work", "walk me through",
      "what is a", "what are", "can you explain", "i don't understand",
      "how do i learn"], "teacher", 4),
    (["explain", "tutorial", "beginner", "basics", "lesson",
      "learning", "course", "understand", "simple explanation",
      "for dummies", "how does"], "teacher", 2),

    (["write a poem", "write lyrics", "brainstorm ideas",
      "come up with", "help me create", "write a song",
      "give me ideas", "creative writing"], "creative", 4),
    (["poem", "lyrics", "brainstorm", "creative", "art",
      "design idea", "invent", "compose", "imagine", "original",
      "artwork", "inspiration", "concept", "vision board"], "creative", 2),

    (["tell me a story", "write me a story", "once upon a time",
      "write a short story", "make up a story",
      "continue the story", "next chapter"], "story", 5),
    (["story", "fiction", "fantasy", "adventure", "narrative",
      "character", "plot", "novel", "tale", "protagonist",
      "villain", "quest", "chapter", "scene", "dialogue"], "story", 2),

    (["pros and cons", "both sides", "which is better",
      "advantages and disadvantages", "argue for and against",
      "compare and contrast", "should i choose between"], "debate", 5),
    (["versus", " vs ", "debate", "compare", "better or worse",
      "tradeoffs", "trade-offs", "advantages", "disadvantages"], "debate", 2),

    (["write an email", "draft an email", "reply to this email",
      "write a cover letter", "prepare a presentation",
      "business proposal", "write a report"], "professional", 4),
    (["email", "meeting", "presentation", "colleague", "client",
      "proposal", "workplace", "deadline", "stakeholder",
      "performance review", "manager", "hr", "interview"], "professional", 2),

    (["executive summary", "board presentation", "investor update",
      "strategic plan", "quarterly review", "market analysis"], "executive", 5),
    (["ceo", "board", "roi", "revenue", "quarterly", "enterprise",
      "investor", "portfolio", "kpi", "c-suite", "strategy",
      "market share", "shareholder", "valuation"], "executive", 3),

    (["academic paper", "write a thesis", "formal letter",
      "legal document", "official statement",
      "write in formal", "scholarly article"], "formal", 5),
    (["formal", "official", "thesis", "citation", "scholarly",
      "legal", "contract", "academic", "bibliography",
      "apa format", "mla format", "literature review"], "formal", 3),

    (["just chatting", "what do you think", "your opinion",
      "talk to me", "let's chat", "what's your favourite"], "casual", 3),
    (["hey", "sup", "bro", "dude", "mate", "lol", "haha",
      "omg", "ngl", "tbh", "fr", "vibe", "chill",
      "funny", "joke", "meme", "random", "bored"], "casual", 2),

    (["true or false", "is it true that", "fact check",
      "what is the correct", "verify this",
      "give me only facts", "no opinions"], "strict", 4),
    (["fact", "accurate", "correct", "definition of",
      "precisely", "exactly", "historically"], "strict", 2),

    (["comprehensive overview", "in-depth analysis",
      "everything about", "full explanation", "thorough breakdown",
      "detailed breakdown", "analyze this in detail"], "deep", 5),
    (["analyze", "analyse", "comprehensive", "detailed",
      "thorough", "elaborate", "in depth", "overview of"], "deep", 2),
]


def detect(text: str) -> str:
    lower = text.lower()
    words = set(re.findall(r'\b\w+\b', lower))
    word_count = len(text.split())
    scores: dict = defaultdict(int)

    for patterns, mode_key, weight in _RULES:
        for pattern in patterns:
            if " " in pattern:
                if pattern in lower:
                    scores[mode_key] += weight
            else:
                if pattern in words:
                    scores[mode_key] += weight // 2 if weight > 2 else weight

    if not scores or max(scores.values()) < 2:
        if word_count <= 4:
            return "brief"
        elif word_count <= 10:
            return "fast"
        elif word_count >= 20:
            return "deep"
        else:
            return "fast"

    return max(scores, key=scores.get)


def get_model(mode_key: str, hw_models: dict) -> str:
    mode = MODES.get(mode_key, MODES["fast"])
    role = mode["role"]
    return hw_models.get(role, hw_models.get("fast", "phi3:mini"))


def get_system(mode_key: str) -> str:
    mode = MODES.get(mode_key, MODES["fast"])
    return mode["system"]


def mode_label(mode_key: str) -> str:
    mode = MODES.get(mode_key, MODES["fast"])
    return f"{mode['emoji']} {mode['name']}"
