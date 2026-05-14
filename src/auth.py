from uuid import uuid4

import streamlit as st

from src.config import settings


def require_passcode() -> bool:
    if st.session_state.get("passcode_ok") is True:
        return True

    expected = settings.app_passcode
    if not expected:
        st.error(
            "APP_PASSCODE is not configured on the server. "
            "Set the APP_PASSCODE environment variable to enable access."
        )
        return False

    st.title("🔒 Job RAG")
    st.markdown("Enter the access passcode to continue.")
    entered = st.text_input("Passcode", type="password", key="_passcode_input")
    submitted = st.button("Continue", type="primary")

    if not submitted:
        return False

    if entered == expected:
        st.session_state["passcode_ok"] = True
        if "session_id" not in st.session_state:
            st.session_state["session_id"] = str(uuid4())
        return True

    st.error("Incorrect passcode.")
    return False
