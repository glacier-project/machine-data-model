from enum import Enum
from dataclasses import dataclass
from typing import Any, List
from typing_extensions import override

class VarOperation(Enum):
    READ = 1
    WRITE = 2
    SUBSCRIBE = 3
    UNSUBSCRIBE = 4

@dataclass
class VariableCall:
    varname:str
    operation:VarOperation      
    args:list
   
    @property
    def get_arg(self, index: int) -> List[Any]:
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
        if not isinstance(other, VariableCall):
            return False
        return self.varname == other.varname and self.operation == other.operation and self.args == other.args
    def __call__(self, *args, **kwds):
        pass
    @property
    def to_dict(self) -> dict:
        return {
            "varname": self.varname,
            "operation": self.operation.name,
            "args": self.args
        }
    @property
    def from_dict(cls, data: dict) -> 'VariableCall':
        return cls(
            varname=data["varname"],
            operation=VarOperation[data["operation"]],
            args=data["args"]
        )
    def __str__(self):
        return (
            f"VariableCall("
            f"varname={self.varname}, "
            f"operation={self.operation}, "
            f"args={self.args})"
        )
    def __repr__(self):
        return self.__str__()

     

    