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
import nevergrad
import datetime
from threading import Lock
import pm4py
import pandas
import math

globalNetTimeout = datetime.timedelta(minutes= 5.0)
globalWorkerTimeout = datetime.timedelta(minutes = 5.0)
server = FastAPI()

globalResultInputSetMatchList = []

instructionQueue = [] #This list holds one list per worker.
optimizerListStoreGlobal = [] #This list holds all optimizers for the runs.

pendingTasks = []
finishedTasks = []

instructionQueueLock = Lock()
globalTaskQueueLock = Lock()
optimizerStoreLock = Lock()
globalResultInputSetMatchLock = Lock()
globalTimeoutLock = Lock()
globalWorkerTimeoutLock = Lock()

@server.get("/")
def access_microserviceServer():
    return{"Information": "This is the entrypoint for the process mining analysis tool. If you want to start the analysis of process mining tools. Please request the requirements form with the cli."}

@server.get("/healthcheck", status_code=200)
def answering_healthcheck():
    return {"status":"ok"}

@server.post("/setGlobalTimeout", status_code= 200)
def setGlobalTimeout(newTimeout: taskAndRequirementsTemplateClasses.timeoutMessage):
    global globalNetTimeout
    with globalTimeoutLock:
        globalNetTimeout = datetime.timedelta(minutes= newTimeout.timeout)
    return

@server.post("/converter", status_code= 200)
def convertLog(conversionMessage: taskAndRequirementsTemplateClasses.conversionDetails):
    if conversionMessage.instruction != "convert":
        raise HTTPException(400, "This instruction should not appear here.")
    else:
        filePathPathObject = pathlib.Path(conversionMessage.file)
        if not filePathPathObject.suffix:
            raise HTTPException(400, "Invalid file name")
        else:
            fileName = conversionMessage.file
            ending = filePathPathObject.suffix
            nameWithoutEnding = filePathPathObject.stem
            targetPath = "./dockerNetworkDirectory/input/" + fileName
            convertedLogPath = "./dockerNetworkDirectory/input/" + nameWithoutEnding + "_converted"
            if pathlib.Path.exists(pathlib.Path(targetPath)):
                if ending == ".xes":
                    protoEventLog = pm4py.read.read_xes(targetPath)
                    eventLog = pm4py.convert_to_dataframe(protoEventLog)
                    eventLog.to_csv(pathlib.Path(convertedLogPath + ".csv"), sep= ";", index= False)
                elif ending == ".csv":
                    protoEventLog = pandas.read_csv(pathlib.Path(targetPath), sep= ";")
                    columnsList = protoEventLog.columns
                    caseId = "someString"
                    activity = "someString"
                    timeStamp = "someString"
                    #extraGroupOption = "someString"
                    for elements in columnsList:
                        if elements.lower() == "case id" or elements.lower() == "case_id" or elements.lower() == "case:concept:name":
                            caseId = elements
                        elif elements.lower() == "activity" or elements.lower() == "concept:name":
                            activity = elements
                        elif elements.lower() == "timestamp" or elements.lower() == "complete timestamp" or elements.lower() == "time:timestamp":
                            timeStamp = elements
                    if caseId != "someString" and activity != "someString" and timeStamp != "someString":
                        eventLog = pm4py.format_dataframe(protoEventLog, case_id= caseId, activity_key= activity, timestamp_key= timeStamp)
                        sortedEventLog = eventLog.sort_values(["case:concept:name", "time:timestamp"])
                    elif caseId != "someString" and activity != "someString":
                        eventLog = pm4py.format_dataframe(protoEventLog, case_id= caseId, activity_key= activity)
                        sortedEventLog = eventLog.sort_values(["case:concept:name"], kind= "stable")
                    else:
                        raise HTTPException(400, "Log can not be converted missing values.")
                    xesEventLog = pm4py.convert_to_event_log(sortedEventLog)
                    pm4py.write_xes(xesEventLog, convertedLogPath + ".xes")
            else:
                raise HTTPException(400, "File does not exist.")
    return

@server.post("/myRequirements", status_code=200)
async def store_algo_requirements(myRequirements: taskAndRequirementsTemplateClasses.algoRequirements):
    with instructionQueueLock:
        with globalWorkerTimeoutLock:
            instructionQueue.append([myRequirements, [], [], datetime.datetime.now() + globalWorkerTimeout]) #Register worker in the instruction queue and initialize its personal queue.
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
    if isinstance(attributes, taskAndRequirementsTemplateClasses.listVariable):
        listInputVariable = taskAndRequirementsTemplateClasses.inputParameterList(name= attributes.name, value= attributes.value)
        return listInputVariable

@server.post("/instruction", status_code=200)
async def startInstructionHandler(task: taskAndRequirementsTemplateClasses.instruction):
    if task.instruction == "start_n_test":
        participantList = []
        with instructionQueueLock:
            for participants in instructionQueue:
                participantList.append(copy.deepcopy(participants[0].identification))
        uniqueTaskIdentifier = uuid.uuid4().hex
        with globalTaskQueueLock:
            pendingTasks.append(taskAndRequirementsTemplateClasses.instructionDetails(instruction= "network_test", instructionId= uniqueTaskIdentifier,  participatingWorkers= participantList, payload= [], finishedSubTasksForCompletion= len(participantList), fileIdList= []))
        with globalTimeoutLock:
            taskDuration = globalNetTimeout
        with instructionQueueLock:
            for workers in instructionQueue:
                currentTime = datetime.datetime.now() + taskDuration
                workers[1].append({"instruction":"start_n_test", "instructionId":uniqueTaskIdentifier, "deadline": currentTime})
        return {"taskId":uniqueTaskIdentifier}
    if task.instruction == "send_template_for_workers":
        returnedRequirements = []
        with instructionQueueLock:
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
        with instructionQueueLock:
            instructionQueueCopied = copy.deepcopy(instructionQueue)
        for algorithms in instructionQueueCopied:
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
    with instructionQueueLock:
        for workers in instructionQueue:
            if workers[0].identification.id == identification.id and workers[0].identification.name == identification.name:
                if workers[1] != []:
                    requestedInstruction = workers[1].pop()
                    return requestedInstruction #send instruction if present
                else:
                    return {"instruction":"no_instruction"} #send no instruction if none is present
    return {"instruction":"send_requirements"} #send registering instruction if there was no matching name id pair

def constructWorkerFilePointerList(searchedTask, newResultStatus):
    workerFilePointerList = []
    for participants in searchedTask.participatingWorkers:
        with instructionQueueLock:
            copiedInstructionQueue = copy.deepcopy(instructionQueue)
        for dataOfWorkers in copiedInstructionQueue:
            if participants.name == dataOfWorkers[0].identification.name and participants.id == dataOfWorkers[0].identification.id:
                for results in dataOfWorkers[2]:
                    if results["instructionId"] == searchedTask.instructionId and results["status"] == newResultStatus:
                        workerFilePointerList.append(taskAndRequirementsTemplateClasses.complexWorkerTaskFilePointer(identification= participants, instructionId= searchedTask.instructionId, fileId= results["fileId"]))
    return workerFilePointerList

@server.post("/result/status", status_code=200)
async def workerReportsResult(newResult: taskAndRequirementsTemplateClasses.instructionStatus):
    with instructionQueueLock:
        instructionQueueCopied = copy.deepcopy(instructionQueue)
    for workers in instructionQueueCopied:
        if workers[0].identification.id == newResult.identification.id and workers[0].identification.name == newResult.identification.name:
            if newResult.status == "network_stable" or newResult.status == "finished_privacy_enhancing_algorithm" or newResult.status == "finished_privacy_enhancing_algorithm_for_auto_compare": #check if result is of eligible type
                count = 0
                appended = False
                with globalTaskQueueLock:
                    copiedPendingTasks = copy.deepcopy(pendingTasks)
                for tasks in copiedPendingTasks: #search in all pending tasks
                    if tasks.instructionId == newResult.instructionId and newResult.identification in tasks.participatingWorkers: #if there is a task with a matching identifier
                        with instructionQueueLock:
                            for realWorkers in instructionQueue:
                                if realWorkers[0].identification == newResult.identification:
                                    realWorkers[2].append({"instructionId":newResult.instructionId, "status":newResult.status, "fileId": newResult.fileId}) #if yes append the result to global reference
                                    workers[2].append({"instructionId":newResult.instructionId, "status":newResult.status, "fileId": newResult.fileId}) #and local reference so it is up to date
                                    appended = True
                if appended == False: #if no notify the worker that he is not part of the workers for this task or didn't specify the right task identifier
                    return {"status":"result_rejected_no_matching_task_or_not_a_participating_worker"}
                with instructionQueueLock:
                    secondInstructionQueueCopy = copy.deepcopy(instructionQueue)
                for workersTest in secondInstructionQueueCopy: #search in all workers
                    for resultObject in workersTest[2]: #for every result they have for the task
                        if newResult.instructionId == resultObject["instructionId"] and newResult.status == resultObject["status"]:
                            count = count + 1 #count them up
                with globalTaskQueueLock:
                    secondCopiedPendingTasks = copy.deepcopy(pendingTasks)
                for searchedTask in secondCopiedPendingTasks:
                    if searchedTask.instructionId == newResult.instructionId:
                        if count == searchedTask.finishedSubTasksForCompletion: #and compare them to the number of subtasks
                            with globalTaskQueueLock:
                                newPendingTasks = [] #if the number was equal remove the task from the pending tasks
                                for actualTasks in pendingTasks:
                                    if actualTasks.instructionId == searchedTask.instructionId:
                                        continue
                                    else:
                                        newPendingTasks.append(actualTasks)
                                pendingTasks[:] = copy.deepcopy(newPendingTasks)
                                print(f"These are the pending tasks 2.: {pendingTasks}", flush= True)
                                alreadyPresent = False
                                for actualFinishedTasks in finishedTasks:
                                    if searchedTask.instructionId == actualFinishedTasks.instructionId:
                                        alreadyPresent = True
                                if not alreadyPresent:
                                    finishedTasks.append(searchedTask) #and append it to the finished tasks
                                print(f"These are the finished tasks 3.: {finishedTasks}", flush= True)
                            if searchedTask.instruction == "comparison" or searchedTask.instruction == "autoCompare":
                                workerFilePointerList = constructWorkerFilePointerList(searchedTask, newResult.status)
                                algoRequirementsList = []
                                for requiredValues in secondInstructionQueueCopy:
                                    algoRequirementsList.append(requiredValues[0])
                                if searchedTask.instruction == "comparison":
                                    analyzer.startAnalyzer(copy.deepcopy(searchedTask), copy.deepcopy(algoRequirementsList), copy.deepcopy(workerFilePointerList)) #copied list to stop working on originals
                                else:
                                    startNextIteration(copy.deepcopy(searchedTask), copy.deepcopy(algoRequirementsList), copy.deepcopy(workerFilePointerList)) #copied list to stop working on originals
                return {"status":"result_accepted"}
            else:
                return {"status":"no_matching_task"}
    return {"status":"unidentified_worker"}

@server.post("/client/result/status", status_code=200)
def sendStatusResultToCli(requestedResult: taskAndRequirementsTemplateClasses.networkResult):
    with globalTaskQueueLock:
        pendingTasksCopy = copy.deepcopy(pendingTasks)
    for tasks in pendingTasksCopy:
        if requestedResult.task == tasks.instruction and requestedResult.instructionId == tasks.instructionId:
            instructionQueueLock.acquire()
            if instructionQueue == []:
                instructionQueueLock.release()
                with globalTaskQueueLock:
                    newPendingTasks = [] #remove requested task from pending tasks if no worker is connected
                    for actualTasks in pendingTasks:
                        if actualTasks.instructionId == requestedResult.instructionId:
                            continue
                        else:
                            newPendingTasks.append(actualTasks)
                    pendingTasks[:] = copy.deepcopy(newPendingTasks)
                return {"status":"no_connected_workers"}
            else:
                instructionQueueLock.release()
            print(f"These are the pending tasks 5.: {pendingTasksCopy}", flush= True)
            return {"status":"pending"}
    with globalTaskQueueLock:
        finishedTasksCopy = copy.deepcopy(finishedTasks)    
    for task in finishedTasksCopy:
        if requestedResult.task == task.instruction and requestedResult.instructionId == task.instructionId:
            #finishedTasks.remove(task)
            return {"status":"finished"}
        print(f"These are the pending tasks 1.: {pendingTasksCopy}", flush= True)
    return {"status":"unable_to_find_task"}

@server.get("/system/requirements", status_code=200)
def sendSystemRequirementsToCli():
    newList = []
    with instructionQueueLock():
        for worker in instructionQueue:
            newList.append(copy.deepcopy(worker[0]))  
    return newList

@server.post("/system/task/", status_code=200)
def sendInstructionsForAnylyses(analysesInstructions: list[taskAndRequirementsTemplateClasses.workerTaskSet | taskAndRequirementsTemplateClasses.logNamesOfTheLog]):
    with globalTimeoutLock:
        timeForExecution = globalNetTimeout
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
                    with instructionQueueLock:
                        instructionQueueCopy = copy.deepcopy(instructionQueue)
                    for correspondingAlgo in instructionQueueCopy: #search for the corresponding requirements
                        if correspondingAlgo[0].identification.name == tasks.identification.name and correspondingAlgo[0].identification.id == tasks.identification.id:
                            if correspondingAlgo[0].inputFormat == "xes": #if the task requires an xes file append the logName with the xesLogName
                                tasks.inputParameters.append(taskAndRequirementsTemplateClasses.inputParameterString(name= "logName", value= xesLogName))
                            else: #else use the csv logName
                                tasks.inputParameters.append(taskAndRequirementsTemplateClasses.inputParameterString(name= "logName", value= csvLogName))
            count = count + 1 #increase count to detect several instances of logs
    if xesLogName == "someString" or csvLogName == "someString": #raise exception if supplied template provides no logs.
        raise HTTPException(400, "It seems that you either didn't provide a log file in your task or that you didn't change the default value.")
    for algoWorkers in instructionQueueCopy:
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
        for participatingWorkers in instructionQueueCopy:
            if participatingWorkers[0].identification.name == participantTask.identification.name and participatingWorkers[0].identification.id == participantTask.identification.id:
                participantList.append(participatingWorkers[0].identification)
                neededForCompletion = neededForCompletion + 1
    uniqueTaskIdentifier = uuid.uuid4().hex
    fileIdentifierList = []
    for ids in range(neededForCompletion):
        newFileIdent = uuid.uuid4().hex
        fileIdentifierList.append(newFileIdent)
    with globalTaskQueueLock:
        pendingTasks.append(taskAndRequirementsTemplateClasses.instructionDetails(instruction= "comparison", instructionId= uniqueTaskIdentifier,  participatingWorkers= participantList, payload= analysesInstructionsForMemory, finishedSubTasksForCompletion= neededForCompletion, fileIdList= fileIdentifierList))
    copiedFileIdList = copy.deepcopy(fileIdentifierList)
    for workerTask in analysesInstructions: #Append all tasks to the workers respective queues.
        with instructionQueueLock:
            for workers in instructionQueue:
                if workers[0].identification.name == workerTask.identification.name and workers[0].identification.id == workerTask.identification.id:
                    currentTime = datetime.datetime.now() + timeForExecution
                    workers[1].append({"instruction":"comparison", "instructionId":uniqueTaskIdentifier, "payload":workerTask, "fileId": copiedFileIdList.pop(), "deadline": currentTime})
    return {"taskId":uniqueTaskIdentifier}

def getNumberOfWorkersForAlgo(algoName):
    countWorkers = 0
    with instructionQueueLock:
        for workers in instructionQueue:
            if workers[0].identification.name == algoName:
                countWorkers = countWorkers + 1
    return countWorkers

def findOutLogs(logs: taskAndRequirementsTemplateClasses.logNamesOfTheLog, name):
    logName = ""
    with instructionQueueLock:
        for requirements in instructionQueue:
            if requirements[0].identification.name == name:
                if requirements[0].inputFormat == "xes":
                    logName = logs.xesLogName
                else:
                    logName = logs.csvLogName
    return taskAndRequirementsTemplateClasses.inputParameterString(name= "logName", value= logName)

def loadScheduleTaskDistribution(algoName, numberOfTasks):
    taskSchedulingList = []
    taskDistribution = []
    with instructionQueueLock:
        instructionQueueCopy = copy.deepcopy(instructionQueue)
    for matchingWorkers in instructionQueueCopy:
        if matchingWorkers[0].identification.name == algoName:
            taskSchedulingList.append([matchingWorkers[0].identification, len(matchingWorkers[1])])
            taskDistribution.append([matchingWorkers[0].identification, 0])
    for instructionCounter in range(numberOfTasks):
        newMin = taskSchedulingList[0]
        for workers in taskSchedulingList:
            if newMin[1] > workers[1]:
                newMin = workers
        for workerTasks in taskSchedulingList:
            if newMin[0].name == workerTasks[0].name and newMin[0].id == workerTasks[0].id:
                workerTasks[1] = workerTasks[1] + 1
        for workerTaskSets in taskDistribution:
            if newMin[0].name == workerTaskSets[0].name and newMin[0].id == workerTaskSets[0].id:
                workerTaskSets[1] = workerTaskSets[1] + 1
    return taskDistribution

def automaticOptimizerTaskDistribution(optimizingTaskId, name):
    with globalTimeoutLock:
        currentTimeForTaskExecution = globalNetTimeout
    with optimizerStoreLock:
        print("Begin distributing comparison tasks.", flush= True)
        intermediateParticipantQueue = []
        for optimizerTask in optimizerListStoreGlobal:
            if optimizerTask["optimizingTaskId"] == optimizingTaskId:
                for optimizers in optimizerTask["listOfOptimizers"]:
                    if optimizers["name"] == name:
                        fileIdentifierList = []
                        algoTaskQueue = []
                        newInstructionId = uuid.uuid4().hex
                        newCandidates = []
                        for candidates in range(optimizers["optimizer"].num_workers):
                            newCandidateSet = optimizers["optimizer"].ask()
                            newCandidates.append([newCandidateSet.value, newCandidateSet])
                        print(f"This is the list of candidates we receive from the optimizer: {newCandidates}", flush= True)
                        for newInput in newCandidates:
                            print(f"This is the current candidate: {newInput}")
                            newInstructionParameterList = []
                            newFileId = uuid.uuid4().hex
                            fileIdentifierList.append(newFileId)
                            #counter = 0
                            newCandidateParameterSet = taskAndRequirementsTemplateClasses.taskParameterMatch(instructionId= newInstructionId, fileId= newFileId, matchingParameters= [], candidate= newInput[1], score= 1000.0)
                            for inputParameters in optimizers["softParameters"]:
                                if isinstance(inputParameters, taskAndRequirementsTemplateClasses.inputParameterInt):
                                    newParameter = taskAndRequirementsTemplateClasses.inputParameterInt(name= copy.copy(inputParameters.name), value= newInput[0][inputParameters.name])
                                    newInstructionParameterList.append(newParameter)
                                    newCandidateParameterSet.matchingParameters.append(taskAndRequirementsTemplateClasses.parameterMatch(name= inputParameters.name, originalValue= newInput[0][inputParameters.name], usedValue= newParameter.value))
                                elif isinstance(inputParameters, taskAndRequirementsTemplateClasses.inputParameterFloat):
                                    newParameter = taskAndRequirementsTemplateClasses.inputParameterFloat(name= copy.copy(inputParameters.name), value= newInput[0][inputParameters.name])                                                                             
                                    newInstructionParameterList.append(newParameter)
                                    newCandidateParameterSet.matchingParameters.append(taskAndRequirementsTemplateClasses.parameterMatch(name= inputParameters.name, originalValue= newInput[0][inputParameters.name], usedValue= newParameter.value))
                                else:
                                    newInstructionParameterList.append(copy.deepcopy(inputParameters))
                                    newCandidateParameterSet.matchingParameters.append(taskAndRequirementsTemplateClasses.parameterMatch(name= inputParameters.name, originalValue= inputParameters.value, usedValue= inputParameters.value))
                                #counter = counter + 1
                            for hardInputParameters in optimizers["hardParameters"]:
                                newInstructionParameterList.append(hardInputParameters)
                            newInstructionParameterList.append(findOutLogs(optimizers["logs"], name))
                            currentTime = datetime.datetime.now() + currentTimeForTaskExecution
                            newTaskObject = {"instruction":"autoCompare", "instructionId":newInstructionId, "payload":newInstructionParameterList, "fileId": newFileId, "deadline": currentTime}
                            print(f"This is the current Task Object immediately after transforming the candidates: {newTaskObject}", flush= True) #This is still fine.
                            algoTaskQueue.append(newTaskObject)
                            optimizers["listOfMatchingParameters"].append(newCandidateParameterSet)
                        optimizers["listOfTaskIds"].append(newInstructionId)
                        neededForCompletion = len(algoTaskQueue) #fine
                        taskDistribution = loadScheduleTaskDistribution(name, neededForCompletion) #fine
                        print(f"This is the task distribution without tasks: {taskDistribution}", flush= True) #This also works.
                        print(f"This is the task queue immediately before the distribution to the workers: {algoTaskQueue}", flush= True) #currently with errors somehow only the same record
                        indexForDistributingTasks = 0
                        for taskWorkers in taskDistribution:
                            newWorkerQueueObject = {"identification":taskWorkers[0], "newTasks": []}
                            if taskWorkers[1] == 0:
                                continue
                            else:
                                for records in range(taskWorkers[1]):
                                    print(f"The current index is: {indexForDistributingTasks} and the current record is: {algoTaskQueue[indexForDistributingTasks]}")
                                    newWorkerQueueObject["newTasks"].append(algoTaskQueue[indexForDistributingTasks])
                                    indexForDistributingTasks = indexForDistributingTasks + 1
                            intermediateParticipantQueue.append(newWorkerQueueObject)
                            print(f"This is the first prototype for the workers queue: {intermediateParticipantQueue}", flush= True)
                        baseForTaskObject = copy.deepcopy(intermediateParticipantQueue)
                        analysesInstructionsForMemory = []
                        for baseElements in baseForTaskObject:
                            for listTasks in baseElements["newTasks"]:
                                newPayloadList = []
                                for parametersInPayload in listTasks["payload"]:
                                    if parametersInPayload.name != "logName":
                                        newPayloadList.append(parametersInPayload)
                                listTasks["payload"] = newPayloadList
                                print(f"This is the new payload list for the task: {listTasks['payload']}")
                        print(f"This is the list for the scheduled tasks: {baseForTaskObject}")
                        for protoTasks in baseForTaskObject:
                            for protoTaskTask in protoTasks["newTasks"]:
                                print(f"This parameter set will be memorized for this worker: {protoTaskTask}")
                                newWorkerTaskSet = taskAndRequirementsTemplateClasses.workerTaskSet(identification= protoTasks["identification"], inputParameters= protoTaskTask["payload"])
                                analysesInstructionsForMemory.append(newWorkerTaskSet)
                        analysesInstructionsForMemory.append(optimizers["logs"])
                        participantList = []
                        for workers in taskDistribution:
                            participantList.append(workers[0])
                        newPendingTask = taskAndRequirementsTemplateClasses.instructionDetails(instruction= "autoCompare", instructionId= newInstructionId,  participatingWorkers= participantList, payload= analysesInstructionsForMemory, finishedSubTasksForCompletion= neededForCompletion, fileIdList= fileIdentifierList)
                        with globalTaskQueueLock:
                            pendingTasks.append(newPendingTask)
                            print(f"The pending tasks are 4.: {pendingTasks}", flush= True)
                        for assignedWorkers in intermediateParticipantQueue:
                            with instructionQueueLock:
                                for currentNetWorkers in instructionQueue:
                                    if assignedWorkers["identification"].name == currentNetWorkers[0].identification.name and assignedWorkers["identification"].id == currentNetWorkers[0].identification.id:
                                        for tasksToAppend in assignedWorkers["newTasks"]:
                                            protoPayload = copy.deepcopy(tasksToAppend["payload"])
                                            tasksToAppend["payload"] = {"identification":assignedWorkers["identification"], "inputParameters":protoPayload}
                                            currentNetWorkers[1].append(tasksToAppend)
    return

@server.post("/system/autotask/", status_code= 200)
def startAutoAnalyses(autoInputTemplate: taskAndRequirementsTemplateClasses.autoComparisonTemplate):
    print("Begin auto comparison.", flush= True)
    logsAccessible, xesLogName, csvLogName = checkIfLogsAvailable(autoInputTemplate.logs)
    if logsAccessible == False:
        raise HTTPException(400, "At least one of the logs was not found.")
    groundTruthLog = pm4py.read.read_xes("./dockerNetworkDirectory/input/" + xesLogName)
    if isinstance(groundTruthLog, pm4py.objects.log.obj.EventLog):
        print("Convert log to pandas.Dataframe.", flush= True)
        groundTruthLog = pm4py.objects.conversion.log.converter.apply(log= groundTruthLog, variant= pm4py.objects.conversion.log.converter.Variants.TO_DATA_FRAME)
        groundTruthLog = analyzer.orderDataFrame(groundTruthLog)
    else:
        groundTruthLog = analyzer.orderDataFrame(groundTruthLog)
        number_of_traces = groundTruthLog["case:concept:name"].nunique()
        max_trace_length = analyzer.getMaxTraceLength(groundTruthLog)
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
        #inputSigmas = []
        #lowerBoundList = []
        #upperBoundList = []
        hardParameters = []
        for fixedParameters in autoInputTemplate.fixedAlgoParameters:
            if fixedParameters.name == uniqueAlgos:
                hardParameters = fixedParameters.fixedParameterList
        with instructionQueueLock:
            instructionQueueCopy = copy.deepcopy(instructionQueue)
        for workers in instructionQueueCopy:
            if uniqueAlgos == workers[0].identification.name:
                requirementsList = workers[0].requirements
        softParameterList = []
        optDict = {}
        for requirement in requirementsList:
            print(f"This is a parameter for the auto comparison: {requirement}")
            if isinstance(requirement, taskAndRequirementsTemplateClasses.algoVariableInt) and requirement.autoAdept:
                lowerBound = None
                upperBound = None
                autoStart = None
                if requirement.lowerBound != None:
                    lowerBound = requirement.lowerBound
                elif requirement.keyWordBoundLower != None:
                    if requirement.keyWordBoundLower == "MAX_TRACE_LENGTH":
                        lowerBound = max_trace_length
                    if requirement.keyWordBoundLower == "NUMBER_OF_TRACES":
                        lowerBound = number_of_traces
                if requirement.upperBound != None:
                    upperBound = requirement.upperBound
                elif requirement.keyWordBoundUpper != None:
                    if requirement.keyWordBoundUpper == "MAX_TRACE_LENGTH":
                        upperBound = max_trace_length
                    if requirement.keyWordBoundUpper == "NUMBER_OF_TRACES":
                        upperBound = number_of_traces
                if requirement.autoStart != None:
                    autoStart = requirement.autoStart
                else:
                    if lowerBound != None:
                        autoStart = lowerBound
                    elif lowerBound == None and upperBound != None:
                        autoStart = upperBound
                    else:
                        autoStart = 0
                if requirement.relativeInitial != None:
                    if requirement.relativeInitial <= 1.0 and requirement.relativeInitial >= 0.0 and upperBound != None and lowerBound != None:
                        autoStart = math.ceil(float(lowerBound)  + (abs(float(upperBound) - float(lowerBound)) * requirement.relativeInitial))
                        if autoStart > upperBound:
                            autoStart = upperBound
                #if requirement.lowerBound is None:
                #    newValueForInputVektor = 0.0
                #else: 
                #    newValueForInputVektor = float(requirement.lowerBound)
                #if requirement.upperBound is None:
                #    newValueForInputVektor = newValueForInputVektor + 5.0
                #else:
                #    newValueForInputVektor = newValueForInputVektor + ((float(requirement.upperBound) - newValueForInputVektor) / 2.0)
                if requirement.choice == "exp_b_2" and upperBound is not None:
                    choiceList = [1]
                    newChoiceParameter = 2
                    while newChoiceParameter < upperBound:
                        choiceList.append(newChoiceParameter)
                        newChoiceParameter = newChoiceParameter * 2                    
                    choiceList.append(upperBound)
                    optDict[requirement.name] = nevergrad.p.TransitionChoice(choiceList)
                elif lowerBound is not None and upperBound is not None:
                    optDict[requirement.name] = nevergrad.p.Scalar(init= autoStart, lower= lowerBound, upper= upperBound).set_integer_casting()
                elif lowerBound is None and upperBound is None:
                    optDict[requirement.name] = nevergrad.p.Scalar(init= autoStart).set_integer_casting() 
                elif lowerBound is not None and upperBound is None:
                    optDict[requirement.name] = nevergrad.p.Scalar(init= autoStart, lower= lowerBound).set_integer_casting() 
                else:
                    optDict[requirement.name] = nevergrad.p.Scalar(init= autoStart, upper= upperBound).set_integer_casting()
                #if requirement.lowerBound is not None and requirement.upperBound is not None:
                    #optDict[requirement.name] = nevergrad.p.Scalar(init= requirement.autoStart, lower= requirement.lowerBound, upper= requirement.upperBound).set_integer_casting()
                #elif requirement.lowerBound is None and requirement.upperBound is None:
                    #optDict[requirement.name] = nevergrad.p.Scalar(init= requirement.autoStart).set_integer_casting() 
                #elif requirement.lowerBound is not None and requirement.upperBound is None:
                    #optDict[requirement.name] = nevergrad.p.Scalar(init= requirement.autoStart, lower= requirement.lowerBound).set_integer_casting() 
                #else:
                    #optDict[requirement.name] = nevergrad.p.Scalar(init= requirement.autoStart, upper= requirement.upperBound).set_integer_casting()
                newValueForInputVektor = requirement.autoStart
                #lowerBoundList.append(requirement.lowerBound)
                #upperBoundList.append(requirement.upperBound)
                #inputSigmas.append(requirement.autoSigma) #newValueForInputVektor * 0.4
                inputVektor.append(newValueForInputVektor)
                softParameterList.append(taskAndRequirementsTemplateClasses.inputParameterInt(name= requirement.name, value= newValueForInputVektor, type= "int")) #int(round(newValueForInputVektor))
            if isinstance(requirement, taskAndRequirementsTemplateClasses.algoVariableFloat) and requirement.autoAdept:
                lowerBound = None
                upperBound = None
                autoStart = None
                if requirement.lowerBound != None:
                    lowerBound = requirement.lowerBound
                elif requirement.keyWordBoundLower != None:
                    if requirement.keyWordBoundLower == "MAX_TRACE_LENGTH":
                        lowerBound = max_trace_length
                    if requirement.keyWordBoundLower == "NUMBER_OF_TRACES":
                        lowerBound = number_of_traces
                if requirement.upperBound != None:
                    upperBound = requirement.upperBound
                elif requirement.keyWordBoundUpper != None:
                    if requirement.keyWordBoundUpper == "MAX_TRACE_LENGTH":
                        upperBound = max_trace_length
                    if requirement.keyWordBoundUpper == "NUMBER_OF_TRACES":
                        upperBound = number_of_traces
                if requirement.autoStart != None:
                    autoStart = requirement.autoStart
                if requirement.relativeInitial != None:
                    if requirement.relativeInitial <= 1.0 and requirement.relativeInitial >= 0.0 and upperBound != None and lowerBound != None:
                        autoStart = lowerBound  + (abs(upperBound - lowerBound) * requirement.relativeInitial)
                        if autoStart > upperBound:
                            autoStart = upperBound
                #if requirement.lowerBound is None:
                #    newValueForInputVektor = 0.0
                #else: 
                #    newValueForInputVektor = requirement.lowerBound
                #if requirement.upperBound is None:
                #    newValueForInputVektor = newValueForInputVektor + 5.0
                #else:
                #    newValueForInputVektor = newValueForInputVektor + ((requirement.upperBound - newValueForInputVektor) / 2.0)
                if requirement.choice == "exp_b_2" and upperBound is not None:
                    choiceList = [1.0]
                    newChoiceParameter = 2.0
                    while newChoiceParameter < upperBound:
                        choiceList.append(newChoiceParameter)
                        newChoiceParameter = newChoiceParameter * 2.0                    
                    choiceList.append(upperBound)
                    optDict[requirement.name] = nevergrad.p.TransitionChoice(choiceList)
                elif lowerBound is not None and upperBound is not None:
                    optDict[requirement.name] = nevergrad.p.Scalar(lower= lowerBound, upper= upperBound)
                elif lowerBound is None and upperBound is None:
                    optDict[requirement.name] = nevergrad.p.Scalar()
                elif lowerBound is not None and upperBound is None:
                    optDict[requirement.name] = nevergrad.p.Scalar(lower= lowerBound)
                else:
                    optDict[requirement.name] = nevergrad.p.Scalar(upper= upperBound) 
                #if requirement.lowerBound is not None and requirement.upperBound is not None:
                    #optDict[requirement.name] = nevergrad.p.Scalar(lower= requirement.lowerBound, upper= requirement.upperBound)
                #elif requirement.lowerBound is None and requirement.upperBound is None:
                    #optDict[requirement.name] = nevergrad.p.Scalar()
                #elif requirement.lowerBound is not None and requirement.upperBound is None:
                    #optDict[requirement.name] = nevergrad.p.Scalar(lower= requirement.lowerBound)
                #else:
                    #optDict[requirement.name] = nevergrad.p.Scalar(upper= requirement.upperBound) 
                newValueForInputVektor = requirement.autoStart
                #lowerBoundList.append(requirement.lowerBound)
                #upperBoundList.append(requirement.upperBound)
                #inputSigmas.append(requirement.autoSigma) #newValueForInputVektor * 0.4
                inputVektor.append(newValueForInputVektor)
                softParameterList.append(taskAndRequirementsTemplateClasses.inputParameterFloat(name= requirement.name, value= newValueForInputVektor, type= "float"))
        #sigmaScalingList = []
        #minSigma = min(inputSigmas)
        #for sigmas in inputSigmas:
        #    sigmaScalingList.append(sigmas / minSigma)
        #print(f"This is the list of input sigmas: {inputSigmas} its scaling list {sigmaScalingList} and this the lowerBoundList: {lowerBoundList} and this is the upperBoundList: {upperBoundList}")
        neverDict = nevergrad.p.Dict(**optDict)
        optimizerList.append({"name":uniqueAlgos, "optimizer": nevergrad.optimizers.NGOpt(parametrization= neverDict, budget= 250, num_workers= getNumberOfWorkersForAlgo(uniqueAlgos)), "listOfTaskIds": [], "hardParameters":hardParameters, "softParameters":softParameterList, "logs":autoInputTemplate.logs, "listOfMatchingParameters": []}) #cma.evolution_strategy.CMAEvolutionStrategy(inputVektor, minSigma, {"bounds": [lowerBoundList, upperBoundList], "maxiter": 100, "ftarget": 0.01, "maxfevals": 1000, "CMA_stds": sigmaScalingList})
    optimizingTaskId = uuid.uuid4().hex
    with optimizerStoreLock:
        optimizerListStoreGlobal.append({"optimizingTaskId":optimizingTaskId, "listOfOptimizers": optimizerList, "fitnessGoal": autoInputTemplate.minimumFitness, "precisionGoal": autoInputTemplate.minimumPrecision})
    for algoNames in algoNamesWithoutDuplicatesList:
        automaticOptimizerTaskDistribution(optimizingTaskId, algoNames)
    return {"taskId": optimizingTaskId}

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
    with instructionQueueLock:
        instructionQueueCopy = copy.deepcopy(instructionQueue)
    for algoName in algoNames:
        algoInputFormat = ""
        for workers in instructionQueueCopy:
            if algoName == workers[0].identification.name:
                algoInputFormat = workers[0].inputFormat
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

def startNextIteration(searchedTask, algoRequirementsList, workerFilePointerList):
    print("Starting a new optimizing generation.", flush= True)
    with optimizerStoreLock:
        optimizerListStoreGlobalCopy = copy.deepcopy(optimizerListStoreGlobal)
    for optimizerTasks in optimizerListStoreGlobalCopy:
        for taskInOptList in optimizerTasks["listOfOptimizers"]:
            for idsOfSubtasks in taskInOptList["listOfTaskIds"]:
                if searchedTask.instructionId == idsOfSubtasks:
                    lokalRunStorage, inputEventLog = analyzer.loaderOfResults(searchedTask, algoRequirementsList, workerFilePointerList)
                    groundTruth = analyzer.generateGroundTruth(inputEventLog)
                    candidateList = []
                    resultList = []
                    for elements in lokalRunStorage:
                        precision = 0
                        fitness = 0
                        resultScore = 1000 
                        newPetriNet, initial, final, successful = analyzer.convertToPetriNet(elements.outputModel)
                        if successful:
                            precision = analyzer.calculatePrecisionOfPetriNet(groundTruth["eventLog"], newPetriNet, initial, final)
                            fitness = analyzer.calculateFitnessOfPetriNet(groundTruth["eventLog"], newPetriNet, initial, final)
                            targetFitness = optimizerTasks["fitnessGoal"]
                            targetPrecision = optimizerTasks["precisionGoal"]
                            resultScore = analyzer.evalRunResultForParameterSearch(precision, fitness, targetPrecision, targetFitness)
                        for parameterMatches in taskInOptList["listOfMatchingParameters"]:
                            if parameterMatches.instructionId == elements.instructionId and parameterMatches.fileId == elements.fileId:
                                #resultSetForOpt = {}
                                #for parameters in parameterMatches.matchingParameters:
                                #    resultSetForOpt[parameters.name] = parameters.originalValue
                                parameterMatches.score = resultScore
                                candidateList.append(parameterMatches) #resultSetForOpt
                                with globalResultInputSetMatchLock:
                                    globalResultInputSetMatchList.append({"parameterMatch": copy.deepcopy(parameterMatches), "resultScore": resultScore})
                                    print(f"This is the global result input parameter set match list: {globalResultInputSetMatchList}")
                        resultList.append(resultScore)
                    print(f"This is the list of candidates: {candidateList} and this is the result list: {resultList} we tell to the optimizer.", flush= True)
                    tellList = list(zip(candidateList, resultList))
                    with optimizerStoreLock:
                        for tasksInGlobalOptimizerStore in optimizerListStoreGlobal:
                            if tasksInGlobalOptimizerStore["optimizingTaskId"] == optimizerTasks["optimizingTaskId"]:
                                for optimizerReal in tasksInGlobalOptimizerStore["listOfOptimizers"]:
                                    if optimizerReal["name"] == taskInOptList["name"]:
                                        newTellList = []
                                        for matchElement, matchElementScore in tellList:
                                            for realParameterMatches in optimizerReal["listOfMatchingParameters"]:
                                                if matchElement.instructionId == realParameterMatches.instructionId and matchElement.fileId == realParameterMatches.fileId:
                                                    realParameterMatches.score = matchElement.score
                                                    newTellListRecord = (realParameterMatches.candidate, matchElementScore)
                                                    newTellList.append(newTellListRecord)
                                        for candidateElement, resultElement in newTellList:
                                            if optimizerReal["optimizer"].num_tell < optimizerReal["optimizer"].budget:     
                                                optimizerReal["optimizer"].tell(candidateElement, resultElement)
                                        shouldWeProceed = True
                                        if optimizerReal["optimizer"].num_tell >= optimizerReal["optimizer"].budget:
                                            shouldWeProceed = False
                    if shouldWeProceed:
                        automaticOptimizerTaskDistribution(optimizingTaskId= optimizerTasks["optimizingTaskId"], name= taskInOptList["name"])
                    else:
                        #This is a list to detect an error
                        scoreListTwo = []
                        with optimizerStoreLock:
                            for globalOptimizerStoreObjects in optimizerListStoreGlobal:
                                if globalOptimizerStoreObjects["optimizingTaskId"] == optimizerTasks["optimizingTaskId"]:
                                    optimizationTargetCounter = 0
                                    for optimizers in globalOptimizerStoreObjects["listOfOptimizers"]:
                                        isfinished = False
                                        if optimizers["optimizer"].num_tell >= optimizers["optimizer"].budget:
                                            isfinished = True
                                        if isfinished:
                                            #print(f"The algorithm {optimizers['name']} finished because of: {isfinished}", flush= True)
                                            #bestCandidate = optimizers["optimizer"].provide_recommendation()
                                            #print(f"The best result of {optimizers['name']} is: {bestCandidate} its value is: {bestCandidate.value}", flush= True)
                                            #print(f"The last sigma of {optimizers['name']} is: {optimizers['optimizer'].sigma}", flush= True)
                                            optimizationTargetCounter = optimizationTargetCounter + 1
                            for currentOptimizerStoreObjects in optimizerListStoreGlobal:
                                if currentOptimizerStoreObjects["optimizingTaskId"] == optimizerTasks["optimizingTaskId"]:
                                    if optimizationTargetCounter == len(currentOptimizerStoreObjects["listOfOptimizers"]):
                                        searchedIdList = []
                                        workerFileRelationList = []
                                        for uniqueAlgos in currentOptimizerStoreObjects["listOfOptimizers"]:
                                            if len(uniqueAlgos["listOfMatchingParameters"]) == 0:
                                                print("Result list is empty for at least one participant. Analysis failed.", flush= True)
                                                return
                                            searchedCandidate = uniqueAlgos["listOfMatchingParameters"][0]
                                            for parameterMatchesInOptList in uniqueAlgos["listOfMatchingParameters"]:

                                                #This is a statement to detect an error
                                                scoreListTwo.append(parameterMatchesInOptList.score)

                                                print(f"This is the current parameter match {parameterMatchesInOptList}", flush= True)
                                                print(f"This is the current score of the parameter: {parameterMatchesInOptList.score}", flush= True)
                                                #if parameterMatchesInOptList == uniqueAlgos["listOfMatchingParameters"][0]:
                                                #    searchedCandidate = parameterMatchesInOptList
                                                #else:
                                                if searchedCandidate.score > parameterMatchesInOptList.score:
                                                    searchedCandidate = parameterMatchesInOptList
                                                print(f"This is the new searched candidate score: {searchedCandidate.score}", flush= True)
                                            #searchedCandidate = uniqueAlgos["optimizer"].provide_recommendation()
                                            searchedInstructionId = searchedCandidate.instructionId
                                            searchedFileId = searchedCandidate.fileId
                                            #for parameterMatchForUniqueAlgo in uniqueAlgos["listOfMatchingParameters"]:
                                                #print(f"This is a parameterMatch: {parameterMatchForUniqueAlgo} and this is the candidate: {searchedCandidate}")
                                                #if searchedCandidate == parameterMatchForUniqueAlgo.candidate: #parameterMatchForUniqueAlgo has no value candidate
                                                    #searchedInstructionId = parameterMatchForUniqueAlgo.instructionId
                                                    #searchedFileId = parameterMatchForUniqueAlgo.fileId
                                            searchedIdList.append({"instructionId": searchedInstructionId, "fileId": searchedFileId, "name": uniqueAlgos["name"]})
                                            #if searchedInstructionId == "someString" or searchedFileId == "someString":
                                            #    print("Analyses failed. Failed to locate at least one result.", flush= True)
                                            #    print(f"This is the searchedIdList: {searchedIdList}")
                                            #    return
                                    else:
                                        print("The analyses is not ready yet at least one optimizer has not finished its tasks yet.", flush=True)
                                        return
                        print(f"This is the searchedIdList: {searchedIdList}", flush= True)
                        multiTaskList = []
                        for ids in searchedIdList:
                            with globalTaskQueueLock:
                                finishedCopiedTasks = copy.deepcopy(finishedTasks)
                                print(f"This is the copy of the finished tasks list: {finishedCopiedTasks}", flush= True)
                            for searchedInstructions in finishedCopiedTasks:
                                print(f"This is the current instruction id from the id list: {ids['instructionId']} this is the file id from the current elment of the id list: {ids['fileId']} and this is the instruction id from the current task in finished tasks: {searchedInstructions.instructionId}", flush= True)
                                if ids["instructionId"] == searchedInstructions.instructionId:
                                    print("Passed the if clause.", flush= True)
                                    multiTaskList.append(searchedInstructions)
                        print(f"This is the multiTaskList: {multiTaskList}", flush= True)
                        for tasks in multiTaskList:
                            subList = copy.deepcopy(constructWorkerFilePointerList(tasks, "finished_privacy_enhancing_algorithm_for_auto_compare"))
                            print(f"This is a subList output: {subList}", flush= True)
                            workerFileRelationList.append(subList)
                        analyzer.enterFinalAnalysis(multiTaskList, algoRequirementsList, workerFileRelationList, copy.deepcopy(optimizerTasks), copy.deepcopy(searchedIdList))
                        print(f"This is the global result input set match list: {globalResultInputSetMatchList}", flush= True)
                        print(f"These are the utility scores the algorithm utilizes for its decision: {scoreListTwo}", flush= True)
    return

def taskKiller():
    with globalTaskQueueLock:
        pendingTasksCopy = pendingTasks
    with instructionQueueLock:
        instructionQueueCopy = copy.deepcopy(instructionQueue)
    expireTaskSearchStructure = []
    
    for workers in instructionQueueCopy:
        newWorkerObject = {"identification": workers[0].identification, "tasksIds": []}
        expireTaskSearchStructure.append(newWorkerObject)
    
    for workersInCopy in instructionQueueCopy:
        for taskObjectsInCopy in workersInCopy[1]:
            if taskObjectsInCopy["instruction"] == "compare" or taskObjectsInCopy["instruction"] == "autoCompare" or taskObjectsInCopy["instruction"] == "start_n_test":
                for workerObject in expireTaskSearchStructure:
                    if workersInCopy.identification.name == workerObject["identification"].name and workersInCopy.identification.id == workerObject["identification"].id:
                        existing = False
                        for idsInCompare in workerObject["taskIds"]:
                            if idsInCompare["instructionId"] == taskObjectsInCopy["instructionId"]:
                                existing = True
                                idsInCompare["tasks"].append(taskObjectsInCopy)
                        if existing == False:
                            newIdObject = {"instructionId": taskObjectsInCopy["instructionId"], "tasks": [], "successfullyRemoved": 0}
                            newIdObject.append(taskObjectsInCopy)
                            workerObject["taskIds"].append(newIdObject)

    expiredPendingParticipants = []
    expiredTasks = []
    for objects in expireTaskSearchStructure:
        for mainTasks in objects["taskIds"]:
            amountOfSubtasks = len(mainTasks["tasks"])
            toBeRemoved = 0
            for subTasks in mainTasks["tasks"]:
                if subTasks["deadline"] < datetime.datetime.now():
                    expiredTasks.append({"identification": objects["identification"], "task": subTasks})
                    toBeRemoved = toBeRemoved + 1
            if toBeRemoved == amountOfSubtasks:
                expiredPendingParticipants.append({"instructionId": mainTasks["instructionId"], "identificationOfParticipant":objects["identification"]})

        with instructionQueueLock:
            for removeWorker in expireTaskSearchStructure:
                for originalWorkers in instructionQueue:
                    if removeWorker["identification"].name == originalWorkers[0].identification.name and removeWorker["identification"].id == originalWorkers[0].identification.id:
                        newQueue = []
                        for tasksInQueue in originalWorkers[1]:
                            if tasksInQueue["instruction"] == "compare" or tasksInQueue["instruction"] == "autoCompare" or tasksInQueue["instruction"] == "start_n_test":
                                presentInRemoveList = False
                                for removeTask in removeWorker["taskIds"]:
                                    if removeTask["instructionId"] == tasksInQueue["instructionId"]:
                                        for subTaskInRemove in removeTask["tasks"]:
                                            if subTaskInRemove["instructionId"] == tasksInQueue["instructionId"] and subTaskInRemove["fileId"] == tasksInQueue["fileId"]:
                                                presentInRemoveList = True
                                                removeTask["successfullyRemoved"] = removeTask["successfullyRemoved"] + 1
                                if presentInRemoveList == False:
                                    newQueue.append(tasksInQueue)
                            else:
                                newQueue.append(tasksInQueue)
                originalWorkers[1] = newQueue

def workerKiller():
    with instructionQueueLock:
        instructionQueueCopy = copy.deepcopy(instructionQueue)
    needsToBeChanged = False
    for workers in instructionQueueCopy:
        if datetime.datetime.now() > workers[3]:
            needsToBeChanged = True
    if needsToBeChanged == True:
        newInstructionQueue = []
        tasksForReassignment = []
        with instructionQueueLock:
            for suspiciousWorkers in instructionQueue:
                if datetime.datetime.now() > suspiciousWorkers[3]:
                    tasksForReassignment.append({"workerType": suspiciousWorkers[0].identification.name, "pendingWorkerInstructions": suspiciousWorkers[1], "finishedWorkerInstructions": suspiciousWorkers[2]})
                    continue
                else:
                    newInstructionQueue.append(suspiciousWorkers)
        #for workersInTime in newInstructionQueue:
            
        #for elements in tasksForReassignment:
            
