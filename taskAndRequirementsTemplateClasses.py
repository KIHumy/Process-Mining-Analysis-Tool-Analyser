from pydantic import BaseModel
from typing import Literal, Any

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
    inputFormat: Literal["xes", "csv"]
    outputStructure: Literal["eventLog", "petriNet", "processTree", "bpmn", "dfg"]
    requirements: list[algoVariableFloat | algoVariableInt | algoVariableBool | stringVariable]

class instruction(BaseModel):
    instruction: str

class instructionStatus(BaseModel):
    identification: algoIdentify
    instructionId: str
    status: str

class networkResult(BaseModel):
    task: str
    instructionId: str

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

class logNamesOfTheLog(BaseModel):
    xesLogName: str
    csvLogName: str
    description: str

class instructionDetails(BaseModel):
    instruction: str
    instructionId: str
    participatingWorkers: list[algoIdentify]
    payload: list

class resultWorkerProcessModel(BaseModel):
    identification: algoIdentify
    inputParameters: list[inputParameterInt | inputParameterFloat | inputParameterString | algoVariableBool]
    outputModel: Any
    additionalOutputData: list