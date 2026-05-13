"""
Singleton state for Streamlit batch analysis polling.

This module is imported (and cached by sys.modules) once per Python process.
app.py imports _batch_state.shared and _batch_state.lock on every Streamlit
rerun — they always resolve to the same objects, surviving st.rerun() cycles.

Plain module-level assignment in app.py (exec-based reruns) would create a
new dict each rerun, severing the background thread from the polling loop.
"""

import threading

shared: dict = {
    "running": False,
    "total": 0,
    "done": 0,
    "current": "",
    "errors": [],
    "results": [],
}

lock = threading.Lock()
