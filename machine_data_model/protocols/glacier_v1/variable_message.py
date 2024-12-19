from dataclasses import dataclass
from enum import Enum
from typing import Any

from typing_extensions import override


class VarOperation(Enum):
    READ = 1
    WRITE = 2
    SUBSCRIBE = 3
    UNSUBSCRIBE = 4


@dataclass(init = True)
class VariableCall:
    varname: str
    operation: VarOperation
    args: list

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
        if not isinstance(other, VariableCall):
            return False
        return (
            self.varname == other.varname
            and self.operation == other.operation
            and self.args == other.args
        )

    @property
    def to_dict(self) -> dict:
        return {
            "varname": self.varname,
            "operation": self.operation.name,
            "args": self.args,
        }

    def __str__(self) -> str:
        return (
            f"VariableCall("
            f"varname={self.varname}, "
            f"operation={self.operation}, "
            f"args={self.args})"
        )

    def __repr__(self) -> str:
        return self.__str__()
