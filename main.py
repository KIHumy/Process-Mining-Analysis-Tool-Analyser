from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Literal
import json
import copy
import pathlib
import taskAndRequirementsTemplateClasses
import uuid
import analyzer


server = FastAPI()

instructionQueue = [] #This list holds one list per worker.

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

@server.post("/instruction", status_code=200)
async def startInstructionHandler(task: taskAndRequirementsTemplateClasses.instruction):
    if task.instruction == "start_n_test":
        participantList = []
        for participants in instructionQueue:
            participantList.append(participants[0].identification)
        uniqueTaskIdentifier = uuid.uuid4().hex
        pendingTasks.append(taskAndRequirementsTemplateClasses.instructionDetails(instruction= "network_test", instructionId= uniqueTaskIdentifier,  participatingWorkers= participantList, payload= []))
        for workers in instructionQueue:
            workers[1].append({"instruction":"start_n_test", "instructionId":uniqueTaskIdentifier})
        return {"taskId":uniqueTaskIdentifier}
    if task.instruction == "send_template_for_workers":
        returnedRequirements = []
        for workers in instructionQueue:
            inputVariables = []
            for attributes in workers[0].requirements:
                if isinstance(attributes, taskAndRequirementsTemplateClasses.algoVariableFloat):
                    floatInputValue = taskAndRequirementsTemplateClasses.inputParameterFloat(name= attributes.name, value= attributes.lowerBound)
                    inputVariables.append(floatInputValue)
                if isinstance(attributes, taskAndRequirementsTemplateClasses.algoVariableInt):
                    intInputValue = taskAndRequirementsTemplateClasses.inputParameterInt(name= attributes.name, value= attributes.lowerBound)
                    inputVariables.append(intInputValue)
                if isinstance(attributes, taskAndRequirementsTemplateClasses.algoVariableBool):
                    inputVariables.append(attributes)
                if isinstance(attributes, taskAndRequirementsTemplateClasses.stringVariable):
                    stringInputValue = taskAndRequirementsTemplateClasses.inputParameterString(name= attributes.name, value= attributes.value)
                    inputVariables.append(stringInputValue)
            newWorkerInputJson = {"name":workers[0].identification.name, "inputParameters":inputVariables}
            returnedRequirements.append(newWorkerInputJson)
        returnedRequirements.append({"xesLogName":"someString", "csvLogName":"someString", "description":"These are the file names of the logs you want to compare."})
        return returnedRequirements
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
                        workers[2].append({"instructionId":newResult.instructionId, "status":newResult.status}) #if yes append the result
                        appended = True
                if appended == False: #if no notify the worker that he is not part of the workers for this task or didn't specify the right task identifier
                    return {"status":"result_rejected_no_matching_task_or_not_a_participating_worker"}
                for workersTest in instructionQueue: #search in all workers
                    if {"instructionId":newResult.instructionId, "status":newResult.status} in workersTest[2]: #if they have a result for the task
                        count = count + 1 #count them up
                for searchedTask in pendingTasks:
                    if searchedTask.instructionId == newResult.instructionId:
                        if count == len(searchedTask.participatingWorkers): #and compare them to the number of workers the task was given to
                            if searchedTask.instruction == "comparison":
                                algoRequirementsList = []
                                for requiredValues in instructionQueue:
                                    algoRequirementsList.append(requiredValues[0])
                                analyzer.startAnalyzer(searchedTask, algoRequirementsList)
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
                        if correspondingAlgo[0].identification.name == tasks.name:
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
    for participantTask in analysesInstructions:
        for participatingWorkers in instructionQueue:
            if participatingWorkers[0].identification.name == participantTask.name:
                participantList.append(participatingWorkers[0].identification)
    uniqueTaskIdentifier = uuid.uuid4().hex
    pendingTasks.append(taskAndRequirementsTemplateClasses.instructionDetails(instruction= "comparison", instructionId= uniqueTaskIdentifier,  participatingWorkers= participantList, payload= analysesInstructionsForMemory))
    for workerTask in analysesInstructions: #Append all tasks to the workers respective queues.
        for workers in instructionQueue:
            if workers[0].identification.name == workerTask.name:
                workers[1].append({"instruction":"comparison", "instructionId":uniqueTaskIdentifier, "payload":workerTask})
    return {"taskId":uniqueTaskIdentifier}