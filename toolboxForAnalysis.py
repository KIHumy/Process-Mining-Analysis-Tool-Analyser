import pm4py
import itertools
import copy

def calculateKAnonymity(inputLog):
    print("This is the k anonymity calculation.", flush= True)
    if isinstance(inputLog, pm4py.objects.log.obj.EventLog):
        traceVariantList = pm4py.statistics.traces.generic.log.case_statistics.get_variant_statistics(inputLog)
        print(f"This is the trace variant list when you have a event log datastructure: {traceVariantList}", flush= True)
    else:
        protoTraceVariantList = pm4py.statistics.variants.pandas.get.get_variants_count(inputLog)
        print(f"This is the proto trace variant list when the log is a pandas dataframe: {protoTraceVariantList}", flush= True)
        traceVariantList = []
        for traces, count in protoTraceVariantList.items():
            newElement = {"variant": list(traces), "count": count}
            traceVariantList.append(newElement)
    print(f"This is the k-Anonymity trace dictionary: {traceVariantList}")
    currentMin = 0
    if traceVariantList != []:
        currentMin = traceVariantList[0]["count"]
    else:
        print("This event log seems to have 0 trace variants.")
        return
    for traceVariants in traceVariantList:
       newCandidate = traceVariants["count"]
       if newCandidate < currentMin:
           currentMin = newCandidate
    return currentMin

def calculateLDiversity(inputLog):
    traceVariantList = pm4py.statistics.traces.generic.log.case_statistics.get_variant_statistics(inputLog)
    print(f"This is the l-diversity trace dictionary: {traceVariantList}")
    logLDiversityList = []
    logTraceList = []
    for elements in traceVariantList:
        logTraceList.append(elements["variant"])
    for traces in traceVariantList:
        traceLDiversityList = []
        activityCheckList = []
        activityCheckList = traces["variant"]
        for activities in activityCheckList:
            subtraceComparisonCounter = 0
            for tracesToBeChecked in logTraceList:
                if activities in tracesToBeChecked:
                    subtraceComparisonCounter = subtraceComparisonCounter + 1
            traceLDiversityList.append(subtraceComparisonCounter)  
        logLDiversityList.append(min(traceLDiversityList))
    min_l_diversity = min(logLDiversityList)
    return min_l_diversity

def calculateLDiversityForDFG(inputDfg):
    print(f"This is the input DFG for the DFG l-diversity: {inputDfg}")
    extractedEdges = inputDfg[0]
    l_diversity = 1
    if extractedEdges == {}:
        return l_diversity
    nodeList = []
    lDiversityList = []
    for start, finish in extractedEdges:
        if start not in nodeList:
            nodeList.append(start)
    for node in nodeList:
        includedInEdges = 0
        for node1, node2 in extractedEdges:
            if node == node1:
                includedInEdges = includedInEdges + 1
        lDiversityList.append(includedInEdges)
    l_diversity = min(lDiversityList)
    return l_diversity

def calculateLDiversityForPetriNet(inputPetriNet):
    print(f"This is the input petri net: {inputPetriNet}")
    transitions = inputPetriNet.transitions
    arcList = inputPetriNet.arcs
    print(arcList)
    nodeList = []
    lDiversityList = []
    for edges in transitions:
        if edges.label not in nodeList:
            nodeList.append(edges.label)
            print(edges.label)
    for nodeLabel in nodeList:
        includedInEdges = 0
        for arc in arcList:
            if isinstance(arc.source, pm4py.objects.petri_net.obj.PetriNet.Place):
                continue
            else:
                if arc.source.label == nodeLabel:
                    includedInEdges = includedInEdges + 1
        lDiversityList.append(includedInEdges)
    l_diversity = min(lDiversityList)
    return l_diversity

def generateCandidateSetList(groundTruthEventLog):
    print("Start with set candidates.", flush= True)
    logActivitySet = set()
    logActivitySet.update(groundTruthEventLog["concept:name"])
    print(f"This is the log activity set: {logActivitySet}", flush= True)
    maxSetLength = len(logActivitySet)
    candidateList = []
    for length in range(1, maxSetLength + 1):
        newLengthCandidates = {"length": length, "candidatesOfLength": list(map(set, itertools.combinations(logActivitySet, length)))}
        candidateList.append(newLengthCandidates)
    print(f"This is the first draft of the candidate list before correction: candidate list {candidateList}")
    #groundTruthCompareList = []
    protoGroundTruthCompareList = list(map(set, pm4py.statistics.variants.pandas.get.get_variants_set(groundTruthEventLog)))
    groundTruthCompareList = []
    for elements in protoGroundTruthCompareList:
        if elements in groundTruthCompareList:
            continue
        else:
            groundTruthCompareList.append(elements)
    print(f"This the groundTruthCompareList with the compression: {groundTruthCompareList}", flush= True)
    print(f"These are the trace variants of the log: {pm4py.statistics.variants.pandas.get.get_variants_set(groundTruthEventLog)}", flush= True)
    #for caseId, trace in groundTruthEventLog:
    #    newtraceSet = set(trace["concept:name"].tolist())
    #    groundTruthCompareList.append(newtraceSet)
    correctedCompareList = []
    for lengthLists in candidateList:
        correctedCandidatesOfLength = []
        for candidateSets in lengthLists["candidatesOfLength"]:
            included = False
            for traceSetInGroundTruth in groundTruthCompareList:
                isitIncluded = candidateSets.issubset(traceSetInGroundTruth)
                if isitIncluded == True:
                    included = True
            if included == True:
                correctedCandidatesOfLength.append(candidateSets)
        if correctedCandidatesOfLength != []:
            newRecord = {"length": lengthLists["length"], "candidatesOfLength": correctedCandidatesOfLength}
            correctedCompareList.append(newRecord)
    print(f"This is the correctedCompareList: {correctedCompareList}", flush= True)
    return correctedCompareList

def generateMatchSetList(correctedCompareList, eventLog):
    print(f"This is the type of the groundTruthLog: {type(eventLog)}", flush= True)
    print(f"These are the columns of the groundTruthLog: {eventLog.columns.tolist()}", flush= True)
    matchList = []
    for lengthSets in correctedCompareList:
        lengthCandidates = []
        for sets in lengthSets["candidatesOfLength"]:
            listOfMatchingTraces = []
            for caseId, trace in eventLog.groupby(pm4py.util.constants.CASE_CONCEPT_NAME):
                traceAsList = trace["concept:name"].tolist()
                print(f"This is a trace as list: {traceAsList}", flush= True)
                print(f"This is what is compared the set: {sets} and: {set(traceAsList)} as well as the result: {sets.issubset(set(traceAsList))}")
                if sets.issubset(set(traceAsList)):
                    listOfMatchingTraces.append(traceAsList)
            if listOfMatchingTraces != []:
                newCandidateObject = {"candidate": sets, "matchingTraces": listOfMatchingTraces}
                lengthCandidates.append(newCandidateObject)
        newLengthRecord = {"length": lengthSets["length"], "candidatesOfLengthWithMatchingTraces": lengthCandidates}
        matchList.append(newLengthRecord)
    print(f"This is the matchList: {matchList}", flush= True)
    return matchList