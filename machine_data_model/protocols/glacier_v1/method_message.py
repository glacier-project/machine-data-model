from dataclasses import dataclass
from typing import Any

from typing_extensions import override


@dataclass(init=True)
class MethodCall:
    method: str
    args: list[Any]

    def has_arg(self, arg: Any) -> bool:
        return arg in self.args

    def __len__(self) -> int:
        return len(self.args)

    def __iter__(self) -> Any:
        return iter(self.args)

    def __getitem__(self, index: int) -> Any:
        return self.args[index]

    def __contains__(self, arg: Any) -> bool:
        return arg in self.args

    @override
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, MethodCall):
            return False
        return self.method == other.method and self.args == other.args

    @property
    def to_dict(self) -> dict:
        return {"method": self.method, "args": self.args}

    def __str__(self) -> str:
        return f"MethodCall" f"(method={self.method}" f", args={self.args})"

    def __repr__(self) -> str:
        return self.__str__()
