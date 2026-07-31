import pm4py
import itertools
import copy
import math

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
    currentMin = 0 #initialize max k-anonymity with 0
    if traceVariantList != []: #if log has trace variants
        currentMin = traceVariantList[0]["count"] #take the count of the first elements as the provisional value for k-anonymity
    else:
        print("This event log seems to have 0 trace variants.")
        return
    for traceVariants in traceVariantList: #for every trace variant
       newCandidate = traceVariants["count"]
       if newCandidate < currentMin: #check if it is smaller than the provisional value for maximal k-anonymity
           currentMin = newCandidate #if yes the count for the current trace variant is the new provisional value for k-anonymity
    return currentMin #return the maximal k-anonymity that is supported by the log.

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
    logActivitySet.update(groundTruthEventLog["concept:name"]) #first we create a set consisting of all sets in the original event log
    print(f"This is the log activity set: {logActivitySet}", flush= True)
    numberOfActivities = len(logActivitySet) #then we count the number of unique activities in the original log
    #maxSetLength = len(logActivitySet)
    #candidateList = []
    #for length in range(1, maxSetLength + 1):
    #    newLengthCandidates = {"length": length, "candidatesOfLength": list(map(set, itertools.combinations(logActivitySet, length)))}
    #    candidateList.append(newLengthCandidates)
    #print(f"This is the first draft of the candidate list before correction: candidate list {candidateList}")
    #groundTruthCompareList = []
    protoGroundTruthCompareList = list(map(frozenset, pm4py.statistics.variants.pandas.get.get_variants_set(groundTruthEventLog))) #now we generate a list of sets of all activity sets in the event log.
    groundTruthCompareList = set()
    groundTruthCompareList.update(protoGroundTruthCompareList) #this list is then used to update this set. Leading to a set that consists of all unique activity sets of all traces in the event log.
    maxSetLength = 0 #then we initialize the maximal activity set length of activity sets in the original log with 0
    for traceActivitySets in groundTruthCompareList: #then we iterate through all unique activity sets of all traces in the original event log
        if len(traceActivitySets) > maxSetLength:
            maxSetLength = len(traceActivitySets) #And update the length whenever we find an activity set that is longer then the current value for the longest activity set in the original log
    candidateList = [] #We initialize the candidate list by creating an empty list.
    lengthArray = [0] #We initialize the length array with 0 for possible activity sets for length 0
    for length in range(1, maxSetLength + 1):
        newLengthCandidates = {"length": length, "candidatesOfLength": set()} #Then we add a record for all lengths up to the maximum set length of activity sets of traces in the original log
        candidateList.append(newLengthCandidates)
        lengthArray.append(math.comb(numberOfActivities, length)) #Additionally, we add a length record that tells us the maximal number of candidates for every length up to the maximal set length of activity sets in the original log
    for traceActivityRoot in groundTruthCompareList: #Then we iterate over all unique activity sets from the original log
        activitySetLength = len(traceActivityRoot) #In each of these iterations we first measure the length of the current activity set
        for lengthCandidate in range(1, activitySetLength + 1): #Then we make iterations from 1 to the length of this activity set
            for lengthElement in candidateList: #For each of these iterations we search for the corresponding record in the candidate list
                if lengthElement["length"] == lengthCandidate:
                    if lengthArray[lengthCandidate] > len(lengthElement["candidatesOfLength"]): #If it does not posses all candidates of the current length from the current iteration
                        newCandidates = list(map(frozenset, itertools.combinations(traceActivityRoot, lengthCandidate))) #we generate all subsets of the given length from the activities of the trace activity set
                        lengthElement["candidatesOfLength"].update(newCandidates) #The we update the candidate list
    #for elements in protoGroundTruthCompareList:
    #    if elements in groundTruthCompareList:
    #        continue
    #    else:
    #        groundTruthCompareList.append(elements)
    print(f"This the groundTruthCompareList with the compression: {groundTruthCompareList}", flush= True)
    print(f"These are the trace variants of the log: {pm4py.statistics.variants.pandas.get.get_variants_set(groundTruthEventLog)}", flush= True)
    #for caseId, trace in groundTruthEventLog:
    #    newtraceSet = set(trace["concept:name"].tolist())
    #    groundTruthCompareList.append(newtraceSet)
    #correctedCompareList = []
    #for lengthLists in candidateList:
    #    correctedCandidatesOfLength = []
    #    for candidateSets in lengthLists["candidatesOfLength"]:
    #        included = False
    #        for traceSetInGroundTruth in groundTruthCompareList:
    #            isitIncluded = candidateSets.issubset(traceSetInGroundTruth)
    #            if isitIncluded == True:
    #                included = True
    #        if included == True:
    #            correctedCandidatesOfLength.append(candidateSets)
    #    if correctedCandidatesOfLength != []:
    #        newRecord = {"length": lengthLists["length"], "candidatesOfLength": correctedCandidatesOfLength}
    #        correctedCompareList.append(newRecord)
    #print(f"This is the correctedCompareList: {correctedCompareList}", flush= True)
    print(f"This is the candidateList: {candidateList}", flush= True)
    return candidateList #The finished candidate list is returned in the end

def generateMatchSetList(correctedCompareList, eventLog): #The corrected compare list is typically the output of generateCandidateSetList() while the eventLog is typically the event log after the privacy preserving algorithm was applied.
    print(f"This is the type of the groundTruthLog: {type(eventLog)}", flush= True)
    print(f"These are the columns of the groundTruthLog: {eventLog.columns.tolist()}", flush= True)
    matchList = [] #This initializes the match list as an empty list
    for lengthSets in correctedCompareList: #Then we go through every length up to the maximal length of the longest trace activity set of the traces in the original event log.
        lengthCandidates = [] #This is the list of candidates for the current length. It is again initialized as an empty list.
        for sets in lengthSets["candidatesOfLength"]: #Now we traverse through all candidate sets of the current length.
            listOfMatchingTraces = [] #For each of them we initialize an empty list that holds all traces matching to it.
            for caseId, trace in eventLog.groupby(pm4py.util.constants.CASE_CONCEPT_NAME): #Then we traverse the anonymized log in a trace wise manner.
                traceAsList = trace["concept:name"].tolist() #For each trace we make a list from its activities.
                print(f"This is a trace as list: {traceAsList}", flush= True)
                print(f"This is what is compared the set: {sets} and: {set(traceAsList)} as well as the result: {sets.issubset(set(traceAsList))}")
                if sets.issubset(set(traceAsList)): #Then we transform the list of the trace into a set and test if our candidate is a subset of this set.
                    listOfMatchingTraces.append(traceAsList) #If the candidate is a subset the trace is attached to the list of its matching traces.
            if listOfMatchingTraces != []: #If the candidate had no matching traces in the anonymized log it is excluded from the resulting list.
                newCandidateObject = {"candidate": sets, "matchingTraces": listOfMatchingTraces} #If it had matching traces a record for the candidate is made.
                lengthCandidates.append(newCandidateObject) #The candidate report is then appended to the candidates for the current length.
        if lengthCandidates != []: #If the current length has no candidate it is not included in the resulting list.
            newLengthRecord = {"length": lengthSets["length"], "candidatesOfLengthWithMatchingTraces": lengthCandidates} #If the current length has at least one candidate it gets a record.
            matchList.append(newLengthRecord) #The record is then added to the resulting list.
    print(f"This is the matchList: {matchList}", flush= True)
    return matchList #The resulting list is then returned.