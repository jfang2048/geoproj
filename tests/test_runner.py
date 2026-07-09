"""Test command runner availability detection."""
from geoproject.webapp.components.runner import command_available, available_commands, COMMAND_SPECS


def test_command_specs_are_defined():
    assert len(COMMAND_SPECS) >= 1


def test_missing_command_not_available():
    assert not command_available("Nonexistent Command")


def test_available_returns_list():
    cmds = available_commands()
    assert isinstance(cmds, list)
