from knowledge_agent.service import AssistantService, split_telegram_text


class FakeAgent:
    def __init__(self) -> None:
        self.session_resets = 0

    async def answer(self, user_message: str) -> str:
        return f"reply: {user_message}"

    async def start_new_session(self) -> str:
        self.session_resets += 1
        return "new-session"


async def test_service_returns_agent_text() -> None:
    service = AssistantService(FakeAgent())

    assert await service.reply("hello") == "reply: hello"


async def test_service_starts_new_session() -> None:
    agent = FakeAgent()
    service = AssistantService(agent)

    await service.start_new_session()

    assert agent.session_resets == 1


def test_short_text_is_not_split() -> None:
    assert split_telegram_text("short", limit=10) == ["short"]


def test_long_text_is_split_without_data_loss() -> None:
    chunks = split_telegram_text("alpha beta gamma", limit=10)

    assert chunks == ["alpha beta", "gamma"]
    assert all(len(chunk) <= 10 for chunk in chunks)
