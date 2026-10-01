"""Tests for the initial package scaffold."""


def test_package_is_importable() -> None:
    """The source package can be discovered after installation."""
    import tetris_trainer

    assert tetris_trainer.__doc__
