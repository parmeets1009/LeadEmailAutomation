"""Hermetic environment for tests: blank every env var that could make
create_app or LLMRouter construct a real external client, regardless of what
is set in the developer's shell."""

HERMETIC_ENV = {
    "ANTHROPIC_API_KEY": "",
    "OPENAI_API_KEY": "",
    "GOOGLE_API_KEY": "",
    "GEMINI_API_KEY": "",
    "APOLLO_API_KEY": "",
    "GMAIL_TOKEN_PATH": "",
    "GOOGLE_TOKEN_PATH": "",
    "OUTLOOK_TOKEN_PATH": "",
    "OUTLOOK_ACCESS_TOKEN": "",
    "APP_BASE_URL": "",
    "UNSUBSCRIBE_SECRET": "",
    "DAILY_SEND_CAP": "",
}
