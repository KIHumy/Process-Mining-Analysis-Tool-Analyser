from pydantic import BaseModel
from typing import Literal, Any

class algoIdentify(BaseModel):
    name: str
    id: str

class algoVariableFloat(BaseModel):
    name: str
    lowerBound: float | None
    upperBound: float | None
    autoAdept: bool
    autoStart: float | None
    autoSigma: float | None
    type: Literal["float"] = "float"

class algoVariableInt(BaseModel):
    name: str
    lowerBound: int | None
    upperBound: int | None
    autoAdept: bool
    autoStart: int | None
    autoSigma: int | None
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

class listVariable(BaseModel):
    name: str
    value: list
    description: str
    type: Literal["list"] = "list"

class algoRequirements(BaseModel):
    identification: algoIdentify
    inputFormat: Literal["xes", "csv"]
    outputStructure: Literal["eventLog", "petriNet", "processTree", "bpmn", "dfg"]
    requirements: list[algoVariableFloat | algoVariableInt | algoVariableBool | stringVariable | listVariable]

class instruction(BaseModel):
    instruction: str

class conversionDetails(BaseModel):
    instruction: str
    file: str

class instructionStatus(BaseModel):
    identification: algoIdentify
    instructionId: str
    status: str
    fileId: str

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

class inputParameterList(BaseModel):
    name: str
    value: list
    type: Literal["list"] = "list"

class workerTaskSet(BaseModel):
    identification: algoIdentify
    inputParameters: list[inputParameterInt | inputParameterFloat | inputParameterString | algoVariableBool | inputParameterList]

class logNamesOfTheLog(BaseModel):
    xesLogName: str
    csvLogName: str
    description: str

class instructionDetails(BaseModel):
    instruction: str
    instructionId: str
    participatingWorkers: list[algoIdentify]
    payload: list
    finishedSubTasksForCompletion: int
    fileIdList: list[str]

class resultWorkerProcessModel(BaseModel):
    identification: algoIdentify
    inputParameters: list[inputParameterInt | inputParameterFloat | inputParameterString | algoVariableBool | inputParameterList]
    outputModel: Any
    additionalOutputData: list
    instructionId: str
    fileId: str
    fileName: str

class algoParameters(BaseModel):
    name: str
    fixedParameterList: list[inputParameterInt | inputParameterFloat | inputParameterString | algoVariableBool | inputParameterList]

class autoComparisonTemplate(BaseModel):
    algoList: list[str]
    minimumPrecision: float
    minimumFitness: float
    logs: logNamesOfTheLog
    fixedAlgoParameters: list[algoParameters]

class complexWorkerTaskFilePointer(BaseModel):
    identification: algoIdentify
    instructionId: str
    fileId: str

class parameterMatch(BaseModel):
    name: str
    originalValue: int | float
    usedValue: int | float


class taskParameterMatch(BaseModel):
    instructionId: str
    fileId: str
    matchingParameters: list[parameterMatch]
    candidate: Any | None
    score: float

class autoCompareInformation(BaseModel):
    autoComparisonId: str
    precisionTarget: float
    fitnessTarget: float

class runEvaluation(BaseModel):
    fileName: str
    precision: float
    fitness: float
    caseDisclosureRisk: list | None
    traceDisclosureRisk: list | None
    k_anonymity: int | None
    inputParameters: list

class algoEvaluation(BaseModel):
    name: str
    evaluationReports: list[runEvaluation]

class groundTruthUtilityAndPrivacyData(BaseModel):
    precision: float
    fitness: float
    k_anonymity: int | None
    caseDisclosureRisk: list | None
    traceDisclosureRisk: list | None

class evaluationReport(BaseModel):
    inputEventLog: logNamesOfTheLog
    taskInformation: autoCompareInformation | str
    evaluationOfAlgos: list[algoEvaluation]
    groundTruthUtilityAndPrivacy: None | groundTruthUtilityAndPrivacyData

class timeoutMessage(BaseModel):
    timeout: float