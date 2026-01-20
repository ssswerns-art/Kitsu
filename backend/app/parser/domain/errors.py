class ParserDomainError(Exception):
    """Base exception for parser domain errors."""
    pass


class ParserCannotOverrideManualError(ParserDomainError):
    """Raised when parser attempts to update an entity with source='manual'."""
    pass


class ParserCannotPublishError(ParserDomainError):
    """Raised when parser attempts to set state to 'published' or 'archived'."""
    pass


class EntityLockedError(ParserDomainError):
    """Raised when parser attempts to update locked fields."""
    pass


class InvalidStateTransitionError(ParserDomainError):
    """Raised when parser attempts an invalid state transition."""
    pass


class ParserPermissionDeniedError(ParserDomainError):
    """Raised when parser lacks required permissions."""
    pass


class ParserCannotDeleteError(ParserDomainError):
    """Raised when parser attempts to delete an entity."""
    pass


class ParserCannotManageReleasesError(ParserDomainError):
    """Raised when parser attempts to create or modify releases."""
    pass
