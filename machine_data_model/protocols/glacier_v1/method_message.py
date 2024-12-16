from dataclasses import dataclass
from typing import Any

from typing_extensions import override


@dataclass(frozen=True)
class MethodCall:
    method: str
    args: list[Any]

    @property
    def get_arg(self, index: int) -> list[Any]:
        return self.args[index]

    @property
    def has_arg(self, arg: Any) -> bool:
        return arg in self.args

    @override
    def __len__(self) -> int:
        return len(self.args)

    @override
    def __iter__(self):
        return iter(self.args)

    @override
    def __getitem__(self, index: int) -> Any:
        return self.args[index]

    @override
    def __contains__(self, arg: Any) -> bool:
        return arg in self.args

    @override
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, MethodCall):
            return False
        return self.method == other.method and self.args == other.args

    def __call__(self, *args, **kwds):
        pass

    @property
    def to_dict(self) -> dict:
        return {"method": self.method, "args": self.args}

    @property
    def from_dict(cls, data: dict) -> "MethodCall":
        return cls(method=data["method"], args=data["args"])

    def __str__(self) -> str:
        return f"MethodCall" f"(method={self.method}" f", args={self.args})"

    def __repr__(self):
        return self.__str__()
