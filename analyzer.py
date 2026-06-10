import pathlib
import pm4py
import pandas
import taskAndRequirementsTemplateClasses
import toolboxForAnalysis

globablAnalyzerStorage = []

def generateGroundTruth(logs):
    groundTruthStorage = {}
    xesLogName = logs.xesLogName #save the logs
    xesUploadPath = pathlib.Path("./dockerNetworkDirectory/input/" + xesLogName)
    xesUploadString = "./dockerNetworkDirectory/input/" + xesLogName
    if pathlib.Path.exists(xesUploadPath) == False:
        print("Log file has been removed from the input folder aborting analysis.", flush= True)
        return {}
    
    groundTruthLog = pm4py.read.read_xes(xesUploadString)
    groundTruthStorage["eventLog"] = groundTruthLog
    groundTruthStorage["dfg"] = pm4py.discovery.discover_dfg(groundTruthLog)
    groundTruthStorage["petriNet"] = pm4py.discovery.discover_petri_net_inductive(groundTruthLog)
    groundTruthStorage["processTree"] = pm4py.discovery.discover_process_tree_inductive(groundTruthLog)
    groundTruthStorage["bpmn"] = pm4py.discovery.discover_bpmn_inductive(groundTruthLog)
    print("Created all process modells of the original event log for the comparison.")
    return groundTruthStorage

def highestModelForComparison(runStorage):
    eventLogCounter = 0
    dfgCounter = 0
    processTreeCounter = 0
    bpmnCounter = 0
    petriNetCounter = 0
    comparisonDataType = "someString"
    for elements in runStorage:
        if isinstance(elements, pm4py.objects.log.obj.EventLog):
            eventLogCounter = eventLogCounter + 1
        if isinstance(elements, pm4py.objects.dfg.obj.DirectlyFollowsGraph):
            dfgCounter = dfgCounter + 1
        if isinstance(elements, pm4py.objects.process_tree.obj.ProcessTree):
            processTreeCounter = processTreeCounter + 1
        if isinstance(elements, pm4py.objects.bpmn.obj.BPMN):
            bpmnCounter = bpmnCounter + 1
        if isinstance(elements, pm4py.objects.petri_net.obj.PetriNet):
            petriNetCounter = petriNetCounter + 1
    
    if eventLogCounter == len(runStorage):
        comparisonDataType = "eventLog"

def startCheckingFunction(precision,fitness):
    print(f"The precision is: {precision}", flush=True)
    print(f"The fitness is: {fitness}", flush= True)

def resultSufficient(groundTruth, runResult):
    print("Begin Testing if the result matches the requirements.")
    if isinstance(runResult.outputModel, pm4py.objects.process_tree.obj.ProcessTree) or isinstance(runResult.outputModel, pm4py.objects.bpmn.obj.BPMN) or isinstance(runResult.outputModel, pm4py.objects.dfg.obj.DirectlyFollowsGraph):
        comparisonObject, initial, final = pm4py.convert.convert_to_petri_net(runResult.outputModel)
    elif isinstance(runResult.outputModel, pm4py.objects.log.obj.EventLog) or isinstance(runResult.outputModel, pandas.DataFrame):
        comparisonObject, initial, final = pm4py.discovery.discover_petri_net_inductive(runResult.outputModel)
        k_anonymity = toolboxForAnalysis.calculateKAnonymity(runResult.outputModel)
        l_diversity = toolboxForAnalysis.calculateLDiversity(runResult.outputModel)
        print(f"The k anonymity of this log is: {k_anonymity}", flush= True)
        print(f"The l-diversity of the log is: {l_diversity}", flush= True)
        dfgFromLog = pm4py.discovery.discover_dfg(runResult.outputModel)
        l_diversity_dfg = toolboxForAnalysis.calculateLDiversityForDFG(dfgFromLog)
        l_diversity_Petri_Net = toolboxForAnalysis.calculateLDiversityForPetriNet(comparisonObject)
        print(f"The l diversity for the petri net is: {l_diversity_Petri_Net}")
        print(f"The l diversity for the dfg process model of this log is: {l_diversity_dfg}")
    else:
        comparisonObject = runResult.outputModel
        initial = comparisonObject.additionalOutputData[0]
        final = comparisonObject.additionalOutputData[1]

    fitnessDict = pm4py.conformance.fitness_token_based_replay(groundTruth["eventLog"], comparisonObject, initial, final)
    precision = pm4py.conformance.precision_token_based_replay(groundTruth["eventLog"], comparisonObject, initial, final)
    fitness = fitnessDict["average_trace_fitness"]
    startCheckingFunction(precision, fitness)

def startAnalyzer(inputTask, requirementsList, workerFilePointerList):
    print("Starting the analyzer.", flush= True)
    lokalRunStorage = []
    taskDetails = inputTask.payload
    print("The task is: ", taskDetails)
    inputParameterList = []
    for elements in taskDetails:
        if isinstance(elements, taskAndRequirementsTemplateClasses.logNamesOfTheLog):
            inputEventLog = elements
            print(inputEventLog, flush=True)
        else:
            inputParameterList.append(elements)
    for workers in inputTask.participatingWorkers:
        outputEnding = ""
        for requirements in requirementsList:
            if workers.name == requirements.identification.name and workers.id == requirements.identification.id:
                if requirements.outputStructure == "eventLog":
                    outputEnding = "xes"
                if requirements.outputStructure == "processTree":
                    outputEnding = "ptml"
                if requirements.outputStructure == "petriNet":
                    outputEnding = "pnml"
                if requirements.outputStructure == "bpmn":
                    outputEnding = "bpmn"
                if requirements.outputStructure == "dfg":
                    outputEnding = "dfg"
        for fileReference in workerFilePointerList:
            if fileReference.identification.name == workers.name and fileReference.identification.id == workers.id:
                uploadFilePath = "./dockerNetworkDirectory/workerFiles/" + workers.name + "/output/output_" + workers.name.lower() + "_" + workers.id + "_run_" + inputTask.instructionId + "_" + fileReference.fileId + "." + outputEnding
                if pathlib.Path.exists(pathlib.Path(uploadFilePath)):
                    storedParameters = []
                    for parameterSet in inputParameterList:
                            if workers.name == parameterSet.identification.name and workers.id == parameterSet.identification.id:
                                storedParameters = parameterSet.inputParameters
                    if outputEnding == "xes":
                        newLog = pm4py.read.read_xes(uploadFilePath)
                        lokalRunStorage.append(taskAndRequirementsTemplateClasses.resultWorkerProcessModel(identification= workers, inputParameters= storedParameters, outputModel= newLog, additionalOutputData= []))
                    if outputEnding == "ptml":
                        newProcessTree = pm4py.read.read_ptml(uploadFilePath)
                        lokalRunStorage.append(taskAndRequirementsTemplateClasses.resultWorkerProcessModel(identification= workers, inputParameters= storedParameters, outputModel= newProcessTree, additionalOutputData= []))
                    if outputEnding == "pnml":
                        newPetriNet, initial, final = pm4py.read.read_pnml(uploadFilePath)
                        lokalRunStorage.append(taskAndRequirementsTemplateClasses.resultWorkerProcessModel(identification= workers, inputParameters= storedParameters, outputModel= newPetriNet, additionalOutputData= [initial, final]))
                    if outputEnding == "bpmn":
                        newBPMN = pm4py.read.read_bpmn(uploadFilePath)
                        lokalRunStorage.append(taskAndRequirementsTemplateClasses.resultWorkerProcessModel(identification= workers, inputParameters= storedParameters, outputModel= newBPMN, additionalOutputData= []))
                    if outputEnding == "dfg":
                        newDFG = pm4py.read.read_dfg(uploadFilePath)
                        lokalRunStorage.append(taskAndRequirementsTemplateClasses.resultWorkerProcessModel(identification= workers, inputParameters= storedParameters, outputModel= newDFG, additionalOutputData= []))
                    print("Successfully loaded worker output of " + workers.name + ".", flush= True)
                else:
                    print("Worker output was not found.", flush= True)
        
    originalEventLogData = generateGroundTruth(inputEventLog)
    if originalEventLogData == {}:
        print("Failed to acquire the original log. Aborting comparison.")
        return
    for results in lokalRunStorage:
        print(results, flush=True)
        resultSufficient(originalEventLogData, results)

    
    #highestModelForComparison(lokalRunStorage)