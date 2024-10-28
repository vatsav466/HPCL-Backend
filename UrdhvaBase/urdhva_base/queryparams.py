import typing
import fastapi


class QueryParams:
    def __init__(self, q: str = fastapi.Query(None, description="Filter query to be executed against database."),
                 # example: typing.Any = "{'conditions': [{'op': 'OR', 'q': [{'a' > 20, 'b' > 30}, {'c' > 30}]}] -> "
                 #                       "select <fields> from x where (a > 20 AND b > 30) OR (c > 30)",
                 skip: int = 0,
                 limit: int = 100,
                 sort: str = None,
                 fields: str = None,
                 view: str = fastapi.Query(None, description="An Optional parameter for action views, "
                                                             "This parameter will get discarded for api call's")):
        self.q = q
        self.skip = skip
        self.limit = limit
        self.sort = sort
        self.fields = fields
        self.view = view

