"""Errors whose message is shown verbatim to the user (and to Claude) as the tool result."""


class UserError(Exception):
    """An expected failure: missing file, invalid argument, missing optional extra, etc."""
