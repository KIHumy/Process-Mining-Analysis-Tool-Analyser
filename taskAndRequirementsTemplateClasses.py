from pydantic import BaseModel
from typing import Literal

class algoIdentify(BaseModel):
    name: str
    id: str

class algoVariableFloat(BaseModel):
    name: str
    lowerBound: float
    upperBound: float
    type: Literal["float"] = "float"

class algoVariableInt(BaseModel):
    name: str
    lowerBound: int
    upperBound: int
    type: Literal["int"] = "int"

class algoVariableBool(BaseModel):
    name: str
    value: bool
    type: Literal["bool"] = "bool"

class stringVariable(BaseModel):
    name: str
    value: str
    description: str
    type: Literal["string"] = "string"

class algoRequirements(BaseModel):
    identification: algoIdentify
    requirements: list[algoVariableFloat | algoVariableInt | algoVariableBool | stringVariable]

class instruction(BaseModel):
    instruction: str

class instructionStatus(BaseModel):
    identification: algoIdentify
    status: str

class networkResult(BaseModel):
    task: str

class inputParameterInt(BaseModel):
    name: str
    #lowerBound: int
    #upperBound: int
    value: int
    type: Literal["int"] = "int"

class inputParameterFloat(BaseModel):
    name: str
    #lowerBound: float
    #upperBound: float
    value: float
    type: Literal["float"] = "float"

class inputParameterString(BaseModel):
    name: str
    value: str
    type: Literal["string"] = "string"

class workerTaskSet(BaseModel):
    name: str
    inputParameters: list[inputParameterInt | inputParameterFloat | inputParameterString | algoVariableBool]