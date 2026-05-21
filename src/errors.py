class ShogiSfenReaderError(Exception):
    """Base exception for user-facing reader failures."""


class ConfigError(ShogiSfenReaderError):
    """Raised when config.yaml is invalid."""


class ImageLoadError(ShogiSfenReaderError):
    """Raised when an input image cannot be loaded."""


class RecognitionError(ShogiSfenReaderError):
    """Raised when board or hand recognition is incomplete."""

