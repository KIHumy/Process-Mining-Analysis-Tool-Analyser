from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Literal
import json
import copy
import pathlib
import taskAndRequirementsTemplateClasses
import uuid
import analyzer
import cma


server = FastAPI()

instructionQueue = [] #This list holds one list per worker.
optimizerListStoreGlobal = [] #This list holds all optimizers for the runs.

pendingTasks = []
finishedTasks = []

@server.get("/")
def access_microserviceServer():
    return{"Information": "This is the entrypoint for the process mining analysis tool. If you want to start the analysis of process mining tools. Please request the requirements form with the cli."}

@server.get("/healthcheck", status_code=200)
def answering_healthcheck():
    return {"status":"ok"}

@server.post("/myRequirements", status_code=200)
async def store_algo_requirements(myRequirements: taskAndRequirementsTemplateClasses.algoRequirements):
    instructionQueue.append([myRequirements, [], []]) #Register worker in the instruction queue and initialize its personal queue.
    return {"validity":"status_accepted"}

def transformAlgoVariablesToInputParameters(attributes):
    if isinstance(attributes, taskAndRequirementsTemplateClasses.algoVariableFloat):
        if attributes.lowerBound is None:
            floatInputValue = taskAndRequirementsTemplateClasses.inputParameterFloat(name= attributes.name, value= 0.0)
        else:
            floatInputValue = taskAndRequirementsTemplateClasses.inputParameterFloat(name= attributes.name, value= attributes.lowerBound)
        return floatInputValue
    if isinstance(attributes, taskAndRequirementsTemplateClasses.algoVariableInt):
        if attributes.lowerBound is None:
            intInputValue = taskAndRequirementsTemplateClasses.inputParameterInt(name= attributes.name, value= 0)
        else:
            intInputValue = taskAndRequirementsTemplateClasses.inputParameterInt(name= attributes.name, value= attributes.lowerBound)
        return intInputValue
    if isinstance(attributes, taskAndRequirementsTemplateClasses.algoVariableBool):
        return attributes
    if isinstance(attributes, taskAndRequirementsTemplateClasses.stringVariable):
        stringInputValue = taskAndRequirementsTemplateClasses.inputParameterString(name= attributes.name, value= attributes.value)
        return stringInputValue

@server.post("/instruction", status_code=200)
async def startInstructionHandler(task: taskAndRequirementsTemplateClasses.instruction):
    if task.instruction == "start_n_test":
        participantList = []
        for participants in instructionQueue:
            participantList.append(participants[0].identification)
        uniqueTaskIdentifier = uuid.uuid4().hex
        pendingTasks.append(taskAndRequirementsTemplateClasses.instructionDetails(instruction= "network_test", instructionId= uniqueTaskIdentifier,  participatingWorkers= participantList, payload= [], finishedSubTasksForCompletion= len(participantList), fileIdList= []))
        for workers in instructionQueue:
            workers[1].append({"instruction":"start_n_test", "instructionId":uniqueTaskIdentifier})
        return {"taskId":uniqueTaskIdentifier}
    if task.instruction == "send_template_for_workers":
        returnedRequirements = []
        instructionQueueCopy = copy.deepcopy(instructionQueue)
        for workers in instructionQueueCopy:
            inputVariables = []
            for attributes in workers[0].requirements:    
                inputVariables.append(transformAlgoVariablesToInputParameters(attributes))
            newWorkerInputJson = {"identification":workers[0].identification, "inputParameters":inputVariables}
            returnedRequirements.append(newWorkerInputJson)
        returnedRequirements.append({"xesLogName":"someString", "csvLogName":"someString", "description":"These are the file names of the logs you want to compare."})
        return returnedRequirements
    if task.instruction == "send_auto_template_for_workers":
        availableAlgorithms = []
        availableAlgorithmsParameters = []
        for algorithms in instructionQueue:
            if algorithms[0].identification.name not in availableAlgorithms:
                parameterList = []
                availableAlgorithms.append(algorithms[0].identification.name)
                for parametersForAutoTemplate in algorithms[0].requirements:
                    if isinstance(parametersForAutoTemplate, taskAndRequirementsTemplateClasses.algoVariableFloat) or isinstance(parametersForAutoTemplate, taskAndRequirementsTemplateClasses.algoVariableInt):
                        if parametersForAutoTemplate.autoAdept == False:
                            parameterList.append(transformAlgoVariablesToInputParameters(parametersForAutoTemplate))
                    else:
                        parameterList.append(transformAlgoVariablesToInputParameters(parametersForAutoTemplate))
                availableAlgorithmsParameters.append(taskAndRequirementsTemplateClasses.algoParameters(name= algorithms[0].identification.name, fixedParameterList= parameterList))
        newDefaultLogs = taskAndRequirementsTemplateClasses.logNamesOfTheLog(xesLogName= "someString", csvLogName= "someString", description= "These are the file names of the logs you want to compare.")
        newAutoTemplate = taskAndRequirementsTemplateClasses.autoComparisonTemplate(algoList= availableAlgorithms, minimumPrecision= 0.5, minimumFitness= 0.5, logs= newDefaultLogs, fixedAlgoParameters= availableAlgorithmsParameters)
        return newAutoTemplate
    return {"status":"unknown_instruction"}

@server.post("/task", status_code=200)
async def startWorkerHandler(identification: taskAndRequirementsTemplateClasses.algoIdentify):
    for workers in instructionQueue:
        if workers[0].identification.id == identification.id and workers[0].identification.name == identification.name:
           if workers[1] != []:
                requestedInstruction = workers[1].pop()
                return requestedInstruction #send instruction if present
           else:
               return {"instruction":"no_instruction"} #send no instruction if none is present
    return {"instruction":"send_requirements"} #send registering instruction if there was no matching name id pair

@server.post("/result/status", status_code=200)
async def workerReportsResult(newResult: taskAndRequirementsTemplateClasses.instructionStatus):
    for workers in instructionQueue:
        if workers[0].identification.id == newResult.identification.id and workers[0].identification.name == newResult.identification.name:
            if newResult.status == "network_stable" or newResult.status == "finished_privacy_enhancing_algorithm": #check if result is of eligible type
                count = 0
                appended = False
                for tasks in pendingTasks: #search in all pending tasks
                    if tasks.instructionId == newResult.instructionId and newResult.identification in tasks.participatingWorkers: #if there is a task with a matching identifier
                        workers[2].append({"instructionId":newResult.instructionId, "status":newResult.status, "fileId": newResult.fileId}) #if yes append the result
                        appended = True
                if appended == False: #if no notify the worker that he is not part of the workers for this task or didn't specify the right task identifier
                    return {"status":"result_rejected_no_matching_task_or_not_a_participating_worker"}
                for workersTest in instructionQueue: #search in all workers
                    for resultObject in workersTest[2]: #for every result they have for the task
                        if newResult.instructionId == resultObject["instructionId"] and newResult.status == resultObject["status"]:
                            count = count + 1 #count them up
                for searchedTask in pendingTasks:
                    if searchedTask.instructionId == newResult.instructionId:
                        if count == searchedTask.finishedSubTasksForCompletion: #and compare them to the number of subtasks
                            if searchedTask.instruction == "comparison":
                                algoRequirementsList = []
                                workerFilePointerList = []
                                for participants in searchedTask.participatingWorkers:
                                    for dataOfWorkers in instructionQueue:
                                        if participants.name == dataOfWorkers[0].identification.name and participants.id == dataOfWorkers[0].identification.id:
                                            for results in dataOfWorkers[2]:
                                                if results["instructionId"] == searchedTask.instructionId and results["status"] == newResult.status:
                                                    workerFilePointerList.append(taskAndRequirementsTemplateClasses.complexWorkerTaskFilePointer(identification= participants, instructionId= searchedTask.instructionId, fileId= results["fileId"]))
                                for requiredValues in instructionQueue:
                                    algoRequirementsList.append(requiredValues[0])
                                analyzer.startAnalyzer(searchedTask, algoRequirementsList, workerFilePointerList)
                            pendingTasks.remove(searchedTask) #if the number was equal remove the task from the pending tasks
                            finishedTasks.append(searchedTask) #and append it to the finished tasks
                return {"status":"result_accepted"}
            else:
                return {"status":"no_matching_task"}
    return {"status":"unidentified_worker"}

@server.post("/client/result/status", status_code=200)
def sendStatusResultToCli(requestedResult: taskAndRequirementsTemplateClasses.networkResult):
    for tasks in pendingTasks:
        if requestedResult.task == tasks.instruction and requestedResult.instructionId == tasks.instructionId:
            if instructionQueue == []:
                pendingTasks.remove(tasks) #remove requested task from pending tasks if no worker is connected
                return {"status":"no_connected_workers"}
            return {"status":"pending"}
    for task in finishedTasks:
        if requestedResult.task == task.instruction and requestedResult.instructionId == task.instructionId:
            finishedTasks.remove(task)
            return {"status":"finished"}
        return {"status":"unable_to_find_task"}

@server.get("/system/requirements", status_code=200)
def sendSystemRequirementsToCli():
    newList = []
    for worker in instructionQueue:
      newList.append(worker[0])  
    return newList

@server.post("/system/task/", status_code=200)
def sendInstructionsForAnylyses(analysesInstructions: list[taskAndRequirementsTemplateClasses.workerTaskSet | taskAndRequirementsTemplateClasses.logNamesOfTheLog]):
    count = 0
    xesLogName = "someString"
    csvLogName = "someString"
    csvPath = "someString"
    xesPath = "someString"
    analysesInstructionsForMemory = copy.deepcopy(analysesInstructions)
    print(analysesInstructionsForMemory, flush= True)
    for logs in analysesInstructions:
        if isinstance(logs, taskAndRequirementsTemplateClasses.logNamesOfTheLog): #if the element is the log identifier
            if count > 0: #Function returns an Error if you specify more then one log.
                print("You specified more than one log please only use one log at a time more will not be processed.", flush=True)
                count = 0
                raise HTTPException(400, "You specified more then one Log.")
            xesLogName = logs.xesLogName #save the logs
            csvLogName = logs.csvLogName
            csvPath = pathlib.Path("./dockerNetworkDirectory/input/" +csvLogName)
            xesPath = pathlib.Path("./dockerNetworkDirectory/input/" + xesLogName)
            if pathlib.Path.exists(csvPath) == False:
                raise HTTPException(400, "The csv log file was not found.")
            if pathlib.Path.exists(xesPath) == False:
                raise HTTPException(400, "The xes log file was not found.")
            print("Begin preparing the network file system.")
            analysesInstructions.remove(logs) #remove the element
            
            for tasks in analysesInstructions: #iterate over all tasks for the algorithms
                if isinstance(tasks, taskAndRequirementsTemplateClasses.workerTaskSet):
                    for correspondingAlgo in instructionQueue: #search for the corresponding requirements
                        if correspondingAlgo[0].identification.name == tasks.identification.name and correspondingAlgo[0].identification.id == tasks.identification.id:
                            if correspondingAlgo[0].inputFormat == "xes": #if the task requires an xes file append the logName with the xesLogName
                                tasks.inputParameters.append(taskAndRequirementsTemplateClasses.inputParameterString(name= "logName", value= xesLogName))
                            else: #else use the csv logName
                                tasks.inputParameters.append(taskAndRequirementsTemplateClasses.inputParameterString(name= "logName", value= csvLogName))
            count = count + 1 #increase count to detect several instances of logs
    if xesLogName == "someString" or csvLogName == "someString": #raise exception if supplied template provides no logs.
        raise HTTPException(400, "It seems that you either didn't provide a log file in your task or that you didn't change the default value.")
    for algoWorkers in instructionQueue:
        if algoWorkers[0].inputFormat == "xes":
            #copy xes log in directory
            targetDirectoryXes = pathlib.Path("./dockerNetworkDirectory/workerFiles/" + algoWorkers[0].identification.name + "/input/" + xesLogName)
            targetDirectoryXes.write_bytes(xesPath.read_bytes()) #copy xes log to worker input
        if algoWorkers[0].inputFormat == "csv":
            #copy csv log in directory
            targetDirectoryCsv = pathlib.Path("./dockerNetworkDirectory/workerFiles/" + algoWorkers[0].identification.name + "/input/" + csvLogName)
            targetDirectoryCsv.write_bytes(csvPath.read_bytes()) #copy csv log to worker input
    participantList = []
    neededForCompletion = 0
    for participantTask in analysesInstructions:
        for participatingWorkers in instructionQueue:
            if participatingWorkers[0].identification.name == participantTask.identification.name and participatingWorkers[0].identification.id == participantTask.identification.id:
                participantList.append(participatingWorkers[0].identification)
                neededForCompletion = neededForCompletion + 1
    uniqueTaskIdentifier = uuid.uuid4().hex
    fileIdentifierList = []
    for ids in range(neededForCompletion):
        newFileIdent = uuid.uuid4().hex
        fileIdentifierList.append(newFileIdent)
    pendingTasks.append(taskAndRequirementsTemplateClasses.instructionDetails(instruction= "comparison", instructionId= uniqueTaskIdentifier,  participatingWorkers= participantList, payload= analysesInstructionsForMemory, finishedSubTasksForCompletion= neededForCompletion, fileIdList= fileIdentifierList))
    copiedFileIdList = copy.deepcopy(fileIdentifierList)
    for workerTask in analysesInstructions: #Append all tasks to the workers respective queues.
        for workers in instructionQueue:
            if workers[0].identification.name == workerTask.identification.name and workers[0].identification.id == workerTask.identification.id:
                workers[1].append({"instruction":"comparison", "instructionId":uniqueTaskIdentifier, "payload":workerTask, "fileId": copiedFileIdList.pop()})
    return {"taskId":uniqueTaskIdentifier}

def automaticOptimizerTaskDistribution(optimizingTaskId):
    intermediateWorkerQueueStorage = []
    intermediatePendingTaskStorage = []
    for optimizerTask in optimizerListStoreGlobal:
        if optimizerTask["optimizingTaskId"] == optimizingTaskId:
            for optimizers in optimizerTask["listOfOptimizers"]:
                newInstructionId = uuid.uuid4().hex
                newCandidates = optimizers["optimizer"].ask()
                for newInput in newCandidates:
                    newFileId = uuid.uuid4().hex
                    newTaskObject = {"instruction":"autoCompare", "instructionId":newInstructionId, "payload":workerTask, "fileId": newFileId}
    return

@server.post("system/autotask/", status_code= 200)
def startAutoAnalyses(autoInputTemplate: taskAndRequirementsTemplateClasses.autoComparisonTemplate):
    logsAccessible, xesLogName, csvLogName = checkIfLogsAvailable(autoInputTemplate.logs)
    if logsAccessible == False:
        raise HTTPException(400, "At least one of the logs was not found.")
    taskSchedulingList = []
    algoNamesWithoutDuplicatesList = []
    for algoNamesWithDuplicates in autoInputTemplate.algoList:
        if algoNamesWithDuplicates in algoNamesWithoutDuplicatesList:
            continue
        else:
            algoNamesWithoutDuplicatesList.append(algoNamesWithDuplicates)
    for parameterSetOfAlgo in autoInputTemplate.fixedAlgoParameters: #If you have time remove this unti next hashtag only if you fixed the underlying structure and removed the information redundancy.
        if parameterSetOfAlgo.name not in algoNamesWithoutDuplicatesList:
            raise HTTPException(400, "You specified a parameter Set for an algorithm you didn't include in the algorithms list.")
    checkCounter = 0
    for uniqueAlgosGettingChecked in algoNamesWithoutDuplicatesList:
        for parameterSetsUnderTest in autoInputTemplate.fixedAlgoParameters:
            if uniqueAlgosGettingChecked == parameterSetsUnderTest.name:
                checkCounter = checkCounter + 1
    if checkCounter != len(algoNamesWithoutDuplicatesList):
        raise HTTPException(400, "You provided more parameterSets then algorithms.") #Delete until here.
    loadingSuccessfull = loadLogs(algoNamesWithoutDuplicatesList, xesLogName, csvLogName)
    if loadingSuccessfull == False:
        raise HTTPException(400, "One of you algorithms has no valid input format.")
    optimizerList = []
    for uniqueAlgos in algoNamesWithoutDuplicatesList:
        requirementsList = []
        inputVektor = []
        inputSigmas = []
        lowerBoundList = []
        upperBoundList = []
        hardParameters = []
        for fixedParameters in autoInputTemplate.fixedAlgoParameters:
            if fixedParameters.name == uniqueAlgos:
                hardParameters = fixedParameters.fixedParameterList
        for workers in instructionQueue:
            if uniqueAlgos == workers[0].identification.name:
                requirementsList == workers[0].requirements
        softParameterList = []
        for requirement in requirementsList:
            if isinstance(requirement, taskAndRequirementsTemplateClasses.algoVariableInt) and requirement.autoAdept:
                if requirement.lowerBound is None:
                    newValueForInputVektor = 0.0
                else: 
                    newValueForInputVektor = float(requirement.lowerBound)
                if requirement.upperBound is None:
                    newValueForInputVektor = newValueForInputVektor + 5.0
                else:
                    newValueForInputVektor = newValueForInputVektor + ((float(requirement.upperBound) - newValueForInputVektor) / 2.0)
                lowerBoundList.append(requirement.lowerBound)
                upperBoundList.append(requirement.upperBound)
                inputSigmas.append(newValueForInputVektor * 0.4)
                inputVektor.append(newValueForInputVektor)
                softParameterList.append(taskAndRequirementsTemplateClasses.inputParameterInt(name= requirement.name, value= int(round(newValueForInputVektor)), type= "int"))
            if isinstance(requirement, taskAndRequirementsTemplateClasses.algoVariableFloat) and requirement.autoAdept:
                if requirement.lowerBound is None:
                    newValueForInputVektor = 0.0
                else: 
                    newValueForInputVektor = requirement.lowerBound
                if requirement.upperBound is None:
                    newValueForInputVektor = newValueForInputVektor + 5.0
                else:
                    newValueForInputVektor = newValueForInputVektor + ((requirement.upperBound - newValueForInputVektor) / 2.0)
                lowerBoundList.append(requirement.lowerBound)
                upperBoundList.append(requirement.upperBound)
                inputSigmas.append(newValueForInputVektor * 0.4)
                inputVektor.append(newValueForInputVektor)
                softParameterList.append(taskAndRequirementsTemplateClasses.inputParameterFloat(name= requirement.name, value= newValueForInputVektor, type= "float"))
        optimizerList.append({"name":uniqueAlgos, "optimizer": cma.evolution_strategy.CMAEvolutionStrategy(inputVektor, min(inputSigmas), {"bounds": [lowerBoundList, upperBoundList]}), "listOfTaskIds": [], "hardParameters":hardParameters, "softParameters":softParameterList, "logs":autoInputTemplate.logs})
    optimizingTaskId = uuid.uuid4().hex
    optimizerListStoreGlobal.append({"optimizingTaskId":optimizingTaskId, "listOfOptimizers": optimizerList})
    automaticOptimizerTaskDistribution(optimizingTaskId)
        
    for algoName in algoNamesWithoutDuplicatesList:
        for matchingWorkers in instructionQueue:
            if matchingWorkers[0].identification.name == algoName:
                taskSchedulingList.append([matchingWorkers[0].identification, len(matchingWorkers[1])])
    return

def checkIfLogsAvailable(inputLogs: taskAndRequirementsTemplateClasses):
    xesLogName = inputLogs.xesLogName #save the logs
    csvLogName = inputLogs.csvLogName
    csvPath = pathlib.Path("./dockerNetworkDirectory/input/" + csvLogName)
    xesPath = pathlib.Path("./dockerNetworkDirectory/input/" + xesLogName)
    if pathlib.Path.exists(csvPath) == False or pathlib.Path.exists(xesPath) == False:
        return False, "", "" #returns false if at least one log is missing
    return True, xesLogName, csvLogName #returns true if all logs are available

def loadLogs(algoNames, xesLogName, csvLogName):
    csvPath = pathlib.Path("./dockerNetworkDirectory/input/" + csvLogName)
    xesPath = pathlib.Path("./dockerNetworkDirectory/input/" + xesLogName)
    for algoName in algoNames:
        algoInputFormat = ""
        for workers in instructionQueue:
            if algoName == workers[0].identification.name:
                algoInputFormat = workers.inputFormat
        if algoInputFormat == "":
            return False
        if algoInputFormat == "xes":
            #copy xes log in directory
            targetDirectoryXes = pathlib.Path("./dockerNetworkDirectory/workerFiles/" + algoName + "/input/" + xesLogName)
            targetDirectoryXes.write_bytes(xesPath.read_bytes()) #copy xes log to worker input
        if algoInputFormat == "csv":
            #copy csv log in directory
            targetDirectoryCsv = pathlib.Path("./dockerNetworkDirectory/workerFiles/" + algoName + "/input/" + csvLogName)
            targetDirectoryCsv.write_bytes(csvPath.read_bytes()) #copy csv log to worker input
    return True