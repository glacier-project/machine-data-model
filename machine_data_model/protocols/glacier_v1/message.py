from enum import Enum
from machines import Machines

class MessageTopology(Enum):
    REQUEST = 1
    SUCCESS = 2
    ERROR = 3
    ACCEPTED = 4

class VarOperation(Enum):
    READ = 1
    WRITE = 2
    SUBSCRIBE = 3
    UNSUBSCRIBE = 4

class VariableCall:
    def __init__(self, varname:str, operation:VarOperation, args:list):
        self.varname:str = varname
        self.operation:VarOperation = operation        
        self.args:list = args

class MethodCall:
    def __init__(self, method:str, args:list):
        self.method:str = method
        self.args:list = args

class Message:
    def __init__(self, sender:str, target:str, uuid_code, topology:MessageTopology, payload):
        self.sender:str = sender
        self.target:str = target
        self.uuid_code = uuid_code
        self.topology:MessageTopology = topology
        self.payload = payload

    