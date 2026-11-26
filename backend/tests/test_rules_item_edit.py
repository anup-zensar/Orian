from app.rules.item_edit import CLOSED_REASON, LOCKED_REASON, edit_lock_reason


def lock(closed=False, current="SG0", item="SG0"):
    return edit_lock_reason(transition_closed=closed, current_gate=current, item_gate=item)


def test_any_gate_editable_before_ato_approved():
    for current in ("SG0", "SG3", "SG6_ATO"):
        for item in ("SG0", "SG4_ATD", "SG6_ATO", "CLOSURE"):
            assert lock(current=current, item=item) is None


def test_locked_after_ato_except_closure_items():
    assert lock(current="CLOSURE", item="SG3") == LOCKED_REASON
    assert lock(current="CLOSURE", item="SG6_ATO") == LOCKED_REASON
    assert lock(current="CLOSURE", item="CLOSURE") is None


def test_closed_locks_everything():
    assert lock(closed=True, current="CLOSURE", item="CLOSURE") == CLOSED_REASON
    assert lock(closed=True) == CLOSED_REASON
