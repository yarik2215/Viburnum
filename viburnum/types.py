from typing import Union, Any

HeadersType = dict[str, str]
MultiQueryParamsType = dict[str, list[str]]
JsonData = Union[None, dict[str, Any], list, int, str, float, bool]
