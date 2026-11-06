from app.handlers.requests import _request_status_unchanged


def test_repeating_the_current_request_status_is_detected():
    assert _request_status_unchanged("completed", "completed")
    assert _request_status_unchanged("processing", "processing")
    assert _request_status_unchanged("rejected", "rejected")


def test_changing_the_request_status_is_not_treated_as_a_duplicate():
    assert not _request_status_unchanged("pending", "processing")
    assert not _request_status_unchanged("processing", "completed")
