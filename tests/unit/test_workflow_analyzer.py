from agent.services.workflow_analyzer import analyze_replayability


def test_analyzer_is_analysis_only_and_blocks_replay():
    result = analyze_replayability([{"method": "POST", "resourceType": "XHR"}])
    assert result["replayability"] == "BROWSER_SESSION_REQUIRED"
    assert result["executeAllowed"] is False
    assert result["readOnly"] is True


def test_analyzer_classifies_dom_and_empty_capture():
    assert analyze_replayability([{"method": "GET", "resourceType": "Document"}])["replayability"] == "DOM_FALLBACK"
    assert analyze_replayability([])["replayability"] == "NON_REPLAYABLE"
