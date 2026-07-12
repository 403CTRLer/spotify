"""The capabilities registry is the single source of truth - these tests keep
it honest against the tool definitions and the requested OAuth scopes."""

import inspect

from spotify_mcp.auth.oauth import SCOPES
from spotify_mcp.tools.capabilities import CAPABILITIES
from spotify_mcp.tools.definitions import ALL_TOOLS


def test_registry_matches_tool_definitions_one_to_one():
    assert {tool.__name__ for tool in ALL_TOOLS} == set(CAPABILITIES)


def test_requested_scopes_equal_registry_union():
    # scope audit: adding an endpoint without declaring its scope (or leaving
    # a stale scope in SCOPES) fails here
    declared = set(SCOPES.split())
    union = set().union(*(capability.scopes for capability in CAPABILITIES.values()))
    assert declared == union


def test_confirmation_required_tools_accept_a_confirm_parameter():
    by_name = {tool.__name__: tool for tool in ALL_TOOLS}
    for name, capability in CAPABILITIES.items():
        params = inspect.signature(by_name[name]).parameters
        if capability.confirmation_required:
            assert "confirm" in params, f"{name} declares confirmation but takes no confirm"
        else:
            assert "confirm" not in params, f"{name} takes confirm but does not declare it"


def test_destructive_tools_are_never_marked_read_only():
    for name, capability in CAPABILITIES.items():
        if capability.destructive:
            assert not capability.read_only, name
