from fastapi import FastAPI
from pydantic import BaseModel
from typing import Literal
import json
import taskAndRequirementsTemplateClasses

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
    instructionQueue.append([myRequirements, [], []]) #Register worker in the instuction queue and initialize its personal queue.
    return {"validity":"status_accepted"}

@server.post("/instruction", status_code=200)
async def startInstructionHandler(task: taskAndRequirementsTemplateClasses.instruction):
    if task.instruction == "start_n_test":
        pendingTasks.append("network_test")
        for workers in instructionQueue:
            workers[1].append("start_n_test")
        return {"status":"network_test_initiated"}
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
        return returnedRequirements
    return {"status":"unknown_instruction"}

@server.post("/task", status_code=200)
async def startWorkerHandler(identification: taskAndRequirementsTemplateClasses.algoIdentify):
    for workers in instructionQueue:
        if workers[0].identification.id == identification.id and workers[0].identification.name == identification.name:
           if workers[1] != []:
                requestedInstruction = workers[1].pop()
                return {"instruction":requestedInstruction} #send instruction if present
           else:
               return {"instruction":"no_instruction"} #send no instruction if none is present
    return {"instruction":"send_requirements"} #send registering instruction if there was no matching name id pair

@server.post("/result/status", status_code=200)
async def workerReportsResult(newResult: taskAndRequirementsTemplateClasses.instructionStatus):
    for workers in instructionQueue:
        if workers[0].identification.id == newResult.identification.id and workers[0].identification.name == newResult.identification.name:
            if newResult.status == "network_stable":
                count = 0
                workers[2].append({"status":"network_stable"})
                for workersTest in instructionQueue:
                    if {"status":"network_stable"} in workersTest[2]:
                        count = count + 1
                if count == len(instructionQueue):
                    pendingTasks.remove("network_test")
                    finishedTasks.append("network_test")
                return {"status":"result_accepted"}
            else:
                return {"status":"no_matching_task"}
    return {"status":"unidentified_worker"}

@server.post("/client/result/status", status_code=200)
def sendStatusResultToCli(requestedResult: taskAndRequirementsTemplateClasses.networkResult):
    if requestedResult.task in pendingTasks:
        if instructionQueue == []:
            pendingTasks.remove(requestedResult.task) #remove requested task from pending tasks if no worker is connected
            return {"status":"no_connected_workers"}
        return {"status":"pending"}
    if requestedResult.task in finishedTasks:
        finishedTasks.remove(requestedResult.task)
        return {"status":"finished"}
    return {"status":"unable_to_find_task"}

@server.get("/system/requirements", status_code=200)
def sendSystemRequirementsToCli():
    newList = []
    for worker in instructionQueue:
      newList.append(worker[0])  
    return newList

@server.post("/system/task/", status_code=200)
def sendInstructionsForAnylyses(analysesInstructions: list[taskAndRequirementsTemplateClasses.workerTaskSet]):
    for workerTask in analysesInstructions:
        for workers in instructionQueue:
            if workers[0].identification.name == workerTask.name:
                workers[1].append(workerTask)
    return