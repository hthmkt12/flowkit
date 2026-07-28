import pytest

from agent.services.workflow_adapters import WorkflowAdapterRegistry


def test_registry_exposes_only_reviewed_read_only_adapters():
    registry = WorkflowAdapterRegistry()
    assert registry.list_adapters() == ["get_post_metrics", "read_page_clone"]
    assert registry.inspect("get_post_metrics", {"source": "dom"})["mode"] == "DOM_FALLBACK"
    assert registry.inspect("read_page_clone", {"source": "page"})["mode"] == "SCRAPE_PAGE_CLONE"
    with pytest.raises(PermissionError):
        registry.execute("get_post_metrics", {})


def test_registry_rejects_injected_capability_bypass():
    class AllowEverything:
        def require(self, *_args):
            return None

    with pytest.raises(TypeError, match="sealed"):
        WorkflowAdapterRegistry(AllowEverything())
