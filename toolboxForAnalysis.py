import pm4py

def calculateKAnonymity(inputLog):
    traceVariantList = pm4py.statistics.traces.generic.log.case_statistics.get_variant_statistics(inputLog)
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