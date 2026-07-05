import pathlib
import pm4py
import pandas
import taskAndRequirementsTemplateClasses
import toolboxForAnalysis
import copy
import math
import json


globablAnalyzerStorage = []

def evalRunResultForParameterSearch(precision, fitness, targetPrecision, targetFitness):
    precisionDistance = abs(targetPrecision - precision)
    fitnessDistance = abs(targetFitness - fitness)
    #balance = abs(precisionDistance - fitnessDistance)
    score = precisionDistance + fitnessDistance #+ balance
    print(f"The result for this run result is: {score}")
    return score

def generateGroundTruth(logs):
    groundTruthStorage = {}
    xesLogName = logs.xesLogName #save the logs
    xesUploadPath = pathlib.Path("./dockerNetworkDirectory/input/" + xesLogName)
    xesUploadString = "./dockerNetworkDirectory/input/" + xesLogName
    if pathlib.Path.exists(xesUploadPath) == False:
        print("Log file has been removed from the input folder aborting analysis.", flush= True)
        return {}
    
    groundTruthLog = pm4py.read.read_xes(xesUploadString)
    groundTruthStorage["logFiles"] = copy.deepcopy(logs)
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

#def startCheckingFunction(precision,fitness):
#    print(f"The precision is: {precision}", flush=True)
#    print(f"The fitness is: {fitness}", flush= True)

def convertToPetriNet(processModel):
    print("Begin Testing if the result matches the requirements.", flush= True)
    if isinstance(processModel, pm4py.objects.process_tree.obj.ProcessTree) or isinstance(processModel, pm4py.objects.bpmn.obj.BPMN) or isinstance(processModel, pm4py.objects.dfg.obj.DirectlyFollowsGraph):
        try:
            comparisonObject, initial, final = pm4py.convert.convert_to_petri_net(processModel)
        except Exception as exceptionMessage:
            print(f"The conversion failed with: {exceptionMessage}", flush= True)
            return None, None, None, False
    elif isinstance(processModel, pm4py.objects.log.obj.EventLog) or isinstance(processModel, pandas.DataFrame):
        try:
            comparisonObject, initial, final = pm4py.discovery.discover_petri_net_inductive(processModel)
        except Exception as exceptionMessageTwo:
            print(f"The conversion failed with: {exceptionMessageTwo}", flush= True)
            return None, None, None, False
    else:
        comparisonObject = processModel
        initial = comparisonObject.additionalOutputData[0]
        final = comparisonObject.additionalOutputData[1]

    return comparisonObject, initial, final, True

def calculatePrecisionOfPetriNet(groundTruthEventLog, comparisonObject, initial, final):
    precision = pm4py.conformance.precision_token_based_replay(groundTruthEventLog, comparisonObject, initial, final)
    print(f"The precision is: {precision}", flush=True)
    return precision

def calculateFitnessOfPetriNet(groundTruthEventLog, comparisonObject, initial, final):
    fitnessDict = pm4py.conformance.fitness_token_based_replay(groundTruthEventLog, comparisonObject, initial, final)
    fitness = fitnessDict["average_trace_fitness"]
    print(f"The fitness is: {fitness}", flush= True)
    return fitness

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
    #startCheckingFunction(precision, fitness)

def loaderOfResults(inputTask, requirementsList, workerFilePointerList):
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
                fileName = "output_" + workers.name.lower() + "_" + workers.id + "_run_" + inputTask.instructionId + "_" + fileReference.fileId + "." + outputEnding
                uploadFilePath = "./dockerNetworkDirectory/workerFiles/" + workers.name + "/output/" + fileName
                print(f"Uploading: {uploadFilePath}")
                if pathlib.Path.exists(pathlib.Path(uploadFilePath)):
                    storedParameters = []
                    for parameterSet in inputParameterList:
                            if workers.name == parameterSet.identification.name and workers.id == parameterSet.identification.id:
                                storedParameters = parameterSet.inputParameters
                    if outputEnding == "xes":
                        newLog = pm4py.read.read_xes(uploadFilePath)
                        lokalRunStorage.append(taskAndRequirementsTemplateClasses.resultWorkerProcessModel(identification= workers, inputParameters= storedParameters, outputModel= newLog, additionalOutputData= [], instructionId= inputTask.instructionId, fileId= fileReference.fileId, fileName= fileName))
                    if outputEnding == "ptml":
                        newProcessTree = pm4py.read.read_ptml(uploadFilePath)
                        lokalRunStorage.append(taskAndRequirementsTemplateClasses.resultWorkerProcessModel(identification= workers, inputParameters= storedParameters, outputModel= newProcessTree, additionalOutputData= [], instructionId= inputTask.instructionId, fileId= fileReference.fileId, fileName= fileName))
                    if outputEnding == "pnml":
                        newPetriNet, initial, final = pm4py.read.read_pnml(uploadFilePath)
                        lokalRunStorage.append(taskAndRequirementsTemplateClasses.resultWorkerProcessModel(identification= workers, inputParameters= storedParameters, outputModel= newPetriNet, additionalOutputData= [initial, final], instructionId= inputTask.instructionId, fileId= fileReference.fileId, fileName= fileName))
                    if outputEnding == "bpmn":
                        newBPMN = pm4py.read.read_bpmn(uploadFilePath)
                        lokalRunStorage.append(taskAndRequirementsTemplateClasses.resultWorkerProcessModel(identification= workers, inputParameters= storedParameters, outputModel= newBPMN, additionalOutputData= [], instructionId= inputTask.instructionId, fileId= fileReference.fileId, fileName= fileName))
                    if outputEnding == "dfg":
                        newDFG = pm4py.read.read_dfg(uploadFilePath)
                        lokalRunStorage.append(taskAndRequirementsTemplateClasses.resultWorkerProcessModel(identification= workers, inputParameters= storedParameters, outputModel= newDFG, additionalOutputData= [], instructionId= inputTask.instructionId, fileId= fileReference.fileId, fileName= fileName))
                    print("Successfully loaded worker output of " + workers.name + ".", flush= True)
                else:
                    print("Worker output was not found.", flush= True)
    return lokalRunStorage, inputEventLog

def startAnalyzer(inputTask, requirementsList, workerFilePointerList):
    print("Starting the analyzer.", flush= True)
    
    lokalRunStorage, inputEventLog = loaderOfResults(inputTask, requirementsList, workerFilePointerList)    
    originalEventLogData = generateGroundTruth(inputEventLog)
    if originalEventLogData == {}:
        print("Failed to acquire the original log. Aborting comparison.")
        return
    executeAnalysis(lokalRunStorage, originalEventLogData, None)
    return
    
    #highestModelForComparison(lokalRunStorage)

def enterFinalAnalysis(multiTaskList, algoRequirementsList, workerFileRelationList, optimizingTask, searchedIdList):
    print("Successfully entered final analysis.", flush= True)
    runStorage = []
    inputEventLogList = []
    print(f"This is the multiTaskList: {multiTaskList} and this is the workerFileRelationList: {workerFileRelationList}", flush= True)
    combinedList = copy.deepcopy(list(zip(multiTaskList, workerFileRelationList)))
    print(f"This is the combined List: {combinedList}", flush= True)
    for task, workerFilePointerList in combinedList:
        partialLokalRunStorage, inputEventLog = loaderOfResults(task, algoRequirementsList, workerFilePointerList)
        runStorage.extend(copy.deepcopy(partialLokalRunStorage))
        inputEventLogList.append(inputEventLog)
    print(f"This is the input event log: {inputEventLogList[0]}", flush= True)
    groundTruth = generateGroundTruth(inputEventLogList[0])
    analysesResults = []
    for bestResultIds in searchedIdList:
        for results in runStorage:
            if results.instructionId == bestResultIds["instructionId"] and results.fileId == bestResultIds["fileId"]:
                print("We successfully appended an element to the analyses results.", flush= True)
                analysesResults.append(results)
    print(f"This is the list for the analyses results before we start the next analysis function: {analysesResults}")
    executeAnalysis(analysesResults, groundTruth, taskAndRequirementsTemplateClasses.autoCompareInformation(autoComparisonId= optimizingTask["optimizingTaskId"], precisionTarget= optimizingTask["precisionGoal"], fitnessTarget= optimizingTask["fitnessGoal"]))
    return

def isEmptyModel(outputModel):
    #if isinstance(outputModel, pm4py.objects.process_tree.obj.ProcessTree):
    #    outputModel.
    #if isinstance(outputModel, pm4py.objects.bpmn.obj.BPMN):
    #if isinstance(outputModel, pm4py.objects.dfg.obj.DirectlyFollowsGraph):
    #if isinstance(outputModel, pm4py.objects.log.obj.EventLog) or isinstance(outputModel, pandas.DataFrame):
    #if isinstance(outputModel, pm4py.objects.petri_net.obj.PetriNet):
    #    outputModel.
    return True

def calculateCaseDisclosureRiskForEventLog(groundTruthEventLog, eventLog):
    if isinstance(groundTruthEventLog, pm4py.objects.log.obj.EventLog) or isinstance(eventLog, pm4py.objects.log.obj.EventLog):
        print("At least one input event log is a pm4py event log not a pandas dataframe. Aborting function.", flush= True)
        return
    if isinstance(groundTruthEventLog, pandas.DataFrame) and isinstance(eventLog, pandas.DataFrame):
        print(f"This is the event log when it is a pandas dataframe: {groundTruthEventLog}", flush= True)
        correctedCompareList = toolboxForAnalysis.generateCandidateSetList(groundTruthEventLog)
        generatedMatchList = toolboxForAnalysis.generateMatchSetList(correctedCompareList, eventLog)
        resultList = []
        for lengths in generatedMatchList:
            caseDisclosureRiskForLength = 0.0
            for candidates in lengths["candidatesOfLengthWithMatchingTraces"]:
                candidateDisclosure = (1/len(candidates["matchingTraces"]))/len(lengths["candidatesOfLengthWithMatchingTraces"])
                caseDisclosureRiskForLength = caseDisclosureRiskForLength + candidateDisclosure
            resultList.append({"length": lengths["length"], "caseDisclosureRiskForLength": caseDisclosureRiskForLength})
    return resultList

def calculateTraceDisclosureRiskForEventLog(groundTruthEventLog, eventLog):
    if isinstance(groundTruthEventLog, pm4py.objects.log.obj.EventLog) or isinstance(eventLog, pm4py.objects.log.obj.EventLog):
        print("At least one input event log is a pm4py event log not a pandas dataframe. Aborting function.", flush= True)
        return
    if isinstance(groundTruthEventLog, pandas.DataFrame) and isinstance(eventLog, pandas.DataFrame):
        print(f"This is the event log when it is a pandas dataframe: {groundTruthEventLog}", flush= True)
        correctedCompareList = toolboxForAnalysis.generateCandidateSetList(groundTruthEventLog)
        generatedMatchList = toolboxForAnalysis.generateMatchSetList(correctedCompareList, eventLog)
        traceVariants = pm4py.statistics.variants.pandas.get.get_variants_count(eventLog)
        resultList = []
        #numberOfTraces = float(eventLog[pm4py.util.constants.CASE_CONCEPT_NAME].nunique())
        for lengths in generatedMatchList:
            traceDisclosureRiskForLength = 1.0
            for candidates in lengths["candidatesOfLengthWithMatchingTraces"]:
                uniqueTracesMatchList = []
                numberOfTraces = len(candidates["matchingTraces"])
                for matchingTraces in candidates["matchingTraces"]:
                    if matchingTraces in uniqueTracesMatchList:
                        continue
                    else:
                        uniqueTracesMatchList.append(matchingTraces)
                print(f"This is the list for the unique matching traces: {uniqueTracesMatchList}")
                matchingTracesEntropy = 0.0
                maxEntropy = 0.0
                #lenUniqueTracesMatchList = float(len(uniqueTracesMatchList))
                maxEntropy = -(numberOfTraces * 1/numberOfTraces * math.log2(1/numberOfTraces))
                for elements in uniqueTracesMatchList:
                    occurence = 0.0
                    for trace, count in traceVariants.items():
                        if elements == list(trace):
                            occurence = float(count)
                    #for caseId, traceInResultLog in eventLog:
                    #    if elements == traceInResultLog["concept:name"].tolist():
                    #        occurence = occurence + 1.0
                    #    controlNumber = controlNumber + 1.0
                    #print(f"The control number is: {controlNumber}", flush= True)
                    frequency = occurence / numberOfTraces
                    elementEntropy = frequency * math.log2(frequency)
                    matchingTracesEntropy = matchingTracesEntropy + elementEntropy
                matchingTracesEntropy = -matchingTracesEntropy
                if maxEntropy != 0.0:
                    traceDisclosureRiskForLength = traceDisclosureRiskForLength - (matchingTracesEntropy/maxEntropy)/len(lengths["candidatesOfLengthWithMatchingTraces"])
                else:
                    traceDisclosureRiskForLength = traceDisclosureRiskForLength - (0.0)/len(lengths["candidatesOfLengthWithMatchingTraces"])
                #for traceFrequencies in frequencyStore
                            
                #candidateDisclosure = (1/len(candidates["matchingTraces"]))/len(lengths["candidatesOfLengthWithMatchingTraces"])
                #traceDisclosureRiskForLength = traceDisclosureRiskForLength - candidateDisclosure
            resultList.append({"length": lengths["length"], "traceDisclosureRiskForLength": traceDisclosureRiskForLength})
    return resultList

def executeAnalysis(analysesResults, groundTruth, additionalInformation):
    print(f"These are the analyses results: {analysesResults}", flush= True)
    if additionalInformation == None:
        newEvaluationReport = taskAndRequirementsTemplateClasses.evaluationReport(inputEventLog= groundTruth["logFiles"], taskInformation= "Standard Task", evaluationOfAlgos= [])
    else:
        newEvaluationReport = taskAndRequirementsTemplateClasses.evaluationReport(inputEventLog= groundTruth["logFiles"], taskInformation= additionalInformation, evaluationOfAlgos= [])
    for results in analysesResults:
        petriNet, initial, final, successful = convertToPetriNet(results.outputModel)
        precision = 0
        fitness = 0
        caseDisclosureRiskList = []
        traceDisclosureRiskList = []
        k_anonymity = None
        if successful:
            print(f"This is the groundTruthStorage before it fails: {groundTruth}", flush= True)
            precision = calculatePrecisionOfPetriNet(groundTruth["eventLog"], petriNet, initial, final)
            fitness = calculateFitnessOfPetriNet(groundTruth["eventLog"], petriNet, initial, final)
        print("This is before the if statement.", flush= True)
        if isinstance(results.outputModel, pm4py.objects.log.obj.EventLog) or isinstance(results.outputModel, pandas.DataFrame):
            print("This is after the if statement.", flush= True)
            if isinstance(results.outputModel, pm4py.objects.log.obj.EventLog):
                print("Convert log to pandas.Dataframe.", flush= True)
                resultLog = pm4py.objects.conversion.log.converter.apply(log= results.outputModel, variant= pm4py.objects.conversion.log.converter.Variants.TO_DATA_FRAME)
            else:
                resultLog = results.outputModel
            if isinstance(groundTruth["eventLog"], pm4py.objects.log.obj.EventLog):
                print("Convert log to pandas.Dataframe.", flush= True)
                groundTruthLog = pm4py.objects.conversion.log.converter.apply(log= groundTruth["eventLog"], variant= pm4py.objects.conversion.log.converter.Variants.TO_DATA_FRAME)
            else:
                groundTruthLog = groundTruth["eventLog"]#results.outputModel
            caseDisclosureRiskList = calculateCaseDisclosureRiskForEventLog(groundTruthLog, resultLog)
            traceDisclosureRiskList = calculateTraceDisclosureRiskForEventLog(groundTruthLog, resultLog)
            k_anonymity = toolboxForAnalysis.calculateKAnonymity(resultLog)
        runEvaluation = taskAndRequirementsTemplateClasses.runEvaluation(fileName= results.fileName, precision= precision, fitness= fitness, caseDisclosureRisk= caseDisclosureRiskList, traceDisclosureRisk= traceDisclosureRiskList, k_anonymity= k_anonymity, inputParameters= results.inputParameters)
        exists = False
        for algoEvaluations in newEvaluationReport.evaluationOfAlgos:
            if algoEvaluations.name == results.identification.name:
                algoEvaluations.evaluationReports.append(runEvaluation)
                exists = True
        if exists == False:
            newAlgoEvaluation = taskAndRequirementsTemplateClasses.algoEvaluation(name= results.identification.name, evaluationReports= [])
            newAlgoEvaluation.evaluationReports.append(runEvaluation)
            newEvaluationReport.evaluationOfAlgos.append(newAlgoEvaluation)
    if additionalInformation == None and analysesResults != []:
        ordnerPath = "./dockerNetworkDirectory/output/manual_comparison_" + analysesResults[0].instructionId
    elif additionalInformation == None and analysesResults == []:
        print("The run failed because result list is empty.", flush= True)
        return
    else:
        ordnerPath = "./dockerNetworkDirectory/output/auto_comparison_" + additionalInformation.autoComparisonId
    pathlib.Path(ordnerPath).mkdir(exist_ok= True)
    with open(ordnerPath + "/mainEvaluationReport.json", "w") as openFile:
        json.dump(newEvaluationReport.model_dump(), openFile, indent=3)
    for resultObject in analysesResults:
        loadPath = pathlib.Path("./dockerNetworkDirectory/workerFiles/" + resultObject.identification.name + "/output/" + resultObject.fileName)
        targetDirectory = pathlib.Path(ordnerPath + "/" + resultObject.fileName)
        targetDirectory.write_bytes(loadPath.read_bytes()) #copy xes log to worker input
    return