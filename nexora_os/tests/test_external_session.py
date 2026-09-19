import pytest

from backend.orchestration.external_session import ExternalAgentSession, SessionState


def test_session_rejects_fake_completion_transition():
    session = ExternalAgentSession("cursor", "p", "t")
    session.transition(SessionState.WAITING, "application unavailable")
    with pytest.raises(ValueError):
        session.transition(SessionState.SUCCESS)


def test_session_records_prompt_and_observation():
    session = ExternalAgentSession("cursor", "p", "t")
    session.transition(SessionState.LAUNCHING)
    session.transition(SessionState.READY)
    session.transition(SessionState.PROMPTING)
    session.record_prompt("inspect project", "ACCEPTED")
    session.transition(SessionState.WORKING)
    session.observe({"state": "working", "files_changed": ["README.md"]})
    assert session.prompt_history[0]["delivery_status"] == "ACCEPTED"
    assert session.last_observation["files_changed"] == ["README.md"]
