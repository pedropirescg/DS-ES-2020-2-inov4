import re

class TupleInd:
    def __init__(self, array):
        self.array = array

    def __eq__(self, obj):
        objDef = obj
        if objDef == None:
            return False
        else:
            isEqual = True
            if len(self.array) != len(objDef.array):
                return False
            for i in len(self.array):
                if self.array[i] != objDef.array[i]:
                    return False

            return isEqual

def transpose_matrix(var_type, aux):
    defaultValue = ""
    if "transposezeropercent" in var_type: 
        defaultValue = "0%"
    elif "transposezerotwodigits" in var_type:
        defaultValue = "0.00"
    elif "transposezero" in var_type:
        defaultValue = "0"
    elif "transposenull" in var_type:
        defaultValue = None
    elif "transpose" in var_type: 
        defaultValue = ""
    colNum = len(aux.data[0]) if len(aux.data) > 0 and len(aux.data[0]) > 0 else 0

    if colNum > 0:
        columns = list(set([d[colNum - 2] for d in aux.data]))
        columns.sort()
        
        xAxis = list( set( [ s[:colNum - 2] for s in sorted(aux.data, key=lambda x: x[0]) ] ) )        
        
        result = []
        for xA in xAxis:
            col = list(xA)
            for c in columns:
                filteredTuples = [x[colNum - 1] for x in aux.data if is_equal_until(x, xA, colNum - 2) and x[colNum - 2] == c ]
                col.append(filteredTuples[0] if len(filteredTuples) > 0 else defaultValue)
            result.append(col.copy())

        for i in range(colNum - 3, -1, -1):
            columns.insert(0, aux.cols[i])
        aux.cols = columns


        is_ordered = re.search(r"orderedby[0-9]+|numorderedby[0-9]+|descorderedby[0-9]+|descnumorderedby[0-9]+", var_type)
        if is_ordered:
            ordPrefix = is_ordered.group()
            isAsc = not(ordPrefix.startswith("desc"))
            isNum = "numorderedby" in ordPrefix
            position = int(re.sub("orderedby|numorderedby|descorderedby|descnumorderedby", "", ordPrefix))

            if isNum and isAsc:
                aux.data = sorted(result, key=lambda x: float(x[position]) )
            elif isNum and not(isAsc):
                aux.data = sorted(result, key=lambda x: float(x[position]), reverse=True )
            elif not(isNum) and isAsc:
                aux.data = sorted(result, key=lambda x: x[position] )
            elif not(isNum) and not(isAsc):
                aux.data = sorted(result, key=lambda x: x[position], reverse=True )
        else: 
            aux.data = result.copy()

    var_type = var_type.replace("transposezerotwodigits", "").replace("transposezeropercent", "").replace("transposezero", "").replace('transposenull', '').replace("transpose", "")
    var_type = re.sub("orderedby[0-9]+|numorderedby[0-9]+|descorderedby[0-9]+|descnumorderedby[0-9]+", "", var_type)
    return var_type

def is_equal_until(first, second, index):
    isEqual = True
    for i in range(index):
        if first[i] != second[i]:
            return False

    return isEqual