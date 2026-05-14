from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class FakeSessionState(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as e:
            raise AttributeError(item) from e

    def __setattr__(self, key, value):
        self[key] = value


@pytest.fixture
def passcode_env(monkeypatch):
    monkeypatch.setenv("APP_PASSCODE", "secret")
    import importlib
    import src.config as cfg
    importlib.reload(cfg)
    import src.auth as auth_mod
    importlib.reload(auth_mod)
    yield "secret"


@pytest.fixture
def fake_st(monkeypatch, passcode_env):
    state = FakeSessionState()
    stub = SimpleNamespace(
        session_state=state,
        stop=MagicMock(side_effect=RuntimeError("st.stop")),
        title=MagicMock(),
        text_input=MagicMock(return_value=""),
        button=MagicMock(return_value=False),
        error=MagicMock(),
        info=MagicMock(),
        write=MagicMock(),
        markdown=MagicMock(),
    )
    import src.auth as auth_mod
    monkeypatch.setattr(auth_mod, "st", stub)
    return stub


def test_require_passcode_blocks_when_no_input(fake_st, passcode_env):
    from src import auth
    fake_st.text_input.return_value = ""
    fake_st.button.return_value = False
    result = auth.require_passcode()
    assert result is False
    assert fake_st.session_state.get("passcode_ok") is not True
    assert "session_id" not in fake_st.session_state


def test_require_passcode_accepts_correct_value(fake_st, passcode_env):
    from src import auth
    fake_st.text_input.return_value = "secret"
    fake_st.button.return_value = True
    result = auth.require_passcode()
    assert result is True
    assert fake_st.session_state["passcode_ok"] is True
    sid = fake_st.session_state["session_id"]
    assert isinstance(sid, str) and len(sid) >= 16


def test_require_passcode_rejects_wrong_value(fake_st, passcode_env):
    from src import auth
    fake_st.text_input.return_value = "nope"
    fake_st.button.return_value = True
    result = auth.require_passcode()
    assert result is False
    assert fake_st.session_state.get("passcode_ok") is not True
    fake_st.error.assert_called()
    assert "session_id" not in fake_st.session_state


def test_session_id_minted_once(fake_st, passcode_env):
    from src import auth
    fake_st.text_input.return_value = "secret"
    fake_st.button.return_value = True
    assert auth.require_passcode() is True
    first_sid = fake_st.session_state["session_id"]

    fake_st.text_input.return_value = ""
    fake_st.button.return_value = False
    assert auth.require_passcode() is True
    assert fake_st.session_state["session_id"] == first_sid
