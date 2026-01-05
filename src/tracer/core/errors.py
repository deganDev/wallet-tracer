class TracerError(Exception):
    pass


class DataSourceError(TracerError):
    pass


class RateLimitError(DataSourceError):
    pass
