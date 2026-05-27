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
    return