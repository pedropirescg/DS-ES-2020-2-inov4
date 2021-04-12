import re
import json
import math
import csv
import xlwt as xlwt
import base64
from PIL import Image
from io import BytesIO

#TODO Atualizar com db_client
#from apps.core.views import db_client, get_timezone
from django.db import connections
from django.http import JsonResponse
from django.http import HttpResponse
from django.shortcuts import render
from common.general_classes import AutoCompleteMap
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
# from mvp_project.settings.settings import LOGIN_REDIRECT_URL
# from django.contrib.auth.decorators import login_required
from reposervice.decorators import extract_work, jwt_remote_authentication


from common.general_operations import get_datefilters
from common.matrix_operations import transpose_matrix
from app.customreport.models import CustomCRUD
from app.customreport.models import CustomReport, CustomReportBody, AuxDataReport

from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly, AllowAny, IsAuthenticated
from rest_framework import generics, response, status
from rest_framework.views import APIView

def dumper(obj):
    try:
        return obj.toJSON()
    except:
        return obj.__dict__

class GetReportListEndpoint(APIView):
    @extract_work
    def get(self, request, *args, **kwargs):    
        conf = {}
        dbclient = 'default'
        reports = dict()
        valid_reports = [ c for c in CustomReport.objects.using(dbclient).all().order_by('nome_rep') if c.report_db is None or c.report_db == kwargs['db_key'] ]
        folders = list(set([c.fgrp_rep for c in valid_reports if c.fgrp_rep != '' ]))
        folders.sort()
        for f in folders:
            reports[f] = [c for c in valid_reports if c.fgrp_rep == f]
        conf['folders'] = reports
        conf['reports'] = [c for c in valid_reports]
        conf['items'] = [c for c in valid_reports if c.fgrp_rep == '']

        crud = dict()
        valid_cruds = [c for c in CustomCRUD.objects.using(dbclient).all().order_by('nome_crd') if c.report_db is None or c.report_db == kwargs['db_key'] ]
        folders_crud = list(set([c.fgrp_crd for c in valid_cruds if c.fgrp_crd != '' ]))
        folders_crud.sort()
        for f in folders_crud:
            crud[f] = [c for c in valid_cruds if c.fgrp_crd == f]
        conf['folders_crud'] = crud
        conf['cruds'] = [c for c in valid_cruds]
        conf['items_crud'] = [c for c in valid_cruds if c.fgrp_crd == '']
        
        return HttpResponse(json.dumps(conf, default=dumper), content_type='application/json')

class GetReportHeaderEndpoint(APIView):
    @extract_work
    def get(self, request, *args, **kwargs):
        id = kwargs['id']
        entity_map = AutoCompleteMap.autocompletemap(None, kwargs)
        rep = GetReport(request, id)
        rep['filters'] = [k for k in entity_map]
        rep['fields'] = rep['report'].filters(entity_map)
        rep['report'] = { 'codi_rep': rep['report'].codi_rep, 'nome_rep': rep['report'].nome_rep }
        rep['cell_js'] = json.dumps([{
            'id':r.codi_rbd, 
            'type': view_types(r.type_rbd), 
            'extra': ''
        } for r in rep['cellList'] ])
        rep['cellList'] = [{
            'codi_rbd': x.codi_rbd, 
            'nome_rbd': x.nome_rbd,
            'type_rbd': view_types(x.type_rbd),
            'x': x.x if hasattr(x, 'x') else None, 
            'y': x.y if hasattr(x, 'y') else None, 
            'width': x.width if hasattr(x, 'width') else None, 
            'height': x.height if hasattr(x, 'height') else None,
            'upperclass': x.upperclass if hasattr(x, 'upperclass') else None,
            'bottomclass': x.bottomclass if hasattr(x, 'bottomclass') else None,
            'addContent': json.loads(x.conf_rbd)['addContent']  if 'addContent' in x.conf_rbd else None
        } for x in rep['cellList']]
        rep['valid'] = json.dumps([{'label': f.label, 'id': f.dom_id} for f in rep['fields'] if f.obg])
        
        return HttpResponse(json.dumps(rep, default=dumper), content_type='application/json')

class GetReportBodyEndpoint(APIView):
    #@login_required(login_url=LOGIN_REDIRECT_URL)
    #def get_report_body(request):
    @extract_work
    def post(self, request, *args, **kwargs): 
        #parameters = json.loads(request.POST.get('content'))
        parameters = json.loads(request.data['content'])
        report_data = get_report_body(request, parameters, kwargs)

        return Response(data=json.dumps(report_data.__dict__), status=status.HTTP_200_OK)

class GetReportFileEndpoint(APIView):
    #@login_required(login_url=LOGIN_REDIRECT_URL)
    #def get_file(request):
    def post(self, request, *args, **kwargs):
        if 'format' in request.POST:
            format_img = request.POST.get('format')
            response = HttpResponse(content_type='image/%s'%(format_img))
            response['Content-Disposition'] = 'attachment; filename="relatorio_%s.%s"' % (
                datetime.today().strftime('%Y-%m-%d'), format_img)

            png_b64text = request.POST.get('graphReport')
            im = Image.open(BytesIO(base64.b64decode(png_b64text)))
            new_image = Image.new("RGBA", im.size, "WHITE")
            new_image.paste(im, (0, 0), im)

            if format_img == 'png':
                new_image.save(response, 'PNG')
            elif format_img == 'jpg':
                new_image = new_image.convert('RGB')
                new_image.save(response, 'JPEG')
            elif format_img == 'bmp':
                new_image.save(response, 'BMP')
            #svg http://sachinpatil.com/blog/2013/03/26/python-tips/
        else:
            response = HttpResponse(content_type='application/ms-excel')
            response['Content-Disposition'] = 'attachment; filename="relatorio_%s.xls"' % (
                datetime.today().strftime('%Y-%m-%d'))
            table = request.POST.get('csvReport')
            if table:
                table = table.split('\n')
                table = [t.replace('\r', '').split(';') for t in table]

                wb = xlwt.Workbook(encoding='utf-8')
                ws = wb.add_sheet('Dados')

                font_style = xlwt.XFStyle()
                font_style.font.bold = True

                columns = table[0]

                for col_num in range(len(columns)):
                    ws.write(0, col_num, columns[col_num], font_style)

                font_style = xlwt.XFStyle()

                row_num = 1
                for line in table[1:]:
                    col_num = 0
                    for l in range(len(line)):
                        ws.write(row_num, col_num, line[l], font_style)
                        col_num += 1
                    row_num += 1

                wb.save(response)
            else:
                pass
        return response

def get_report_body(request, parameters, kwargs):
    report_name = ""
    config = {}
    
    try:
        db_client = 'default'
        report_body = CustomReportBody.objects.using(db_client).get(codi_rbd = parameters['idBody'])
        names = report_body.nome_rbd
        config = report_body.conf_rbd
        reportName = names.replace(" ", ".")
    except Exception as e:
        raise e
    
    report_data = GetReportData(request, parameters, kwargs)
    if report_data == None:
        return None

    report_data.config = config
    parameters["type"] = report_body.type_rbd
    if parameters["type"].startswith("transpose"):
        parameters["type"] = transpose_matrix(parameters["type"], report_data)

    if parameters["type"].startswith("rowspantable"):
        parameters["type"] = rowspan_data(parameters["type"], report_data)

    if parameters["type"].startswith("clusteredtable"):
        parameters["type"] = cluster_data(parameters["type"], report_data)

    return report_data

def GetReportData(request, parameters, kwargs):
    result = BuildQuery(request, parameters, kwargs)

    #timezone = get_timezone(request)
    timezone = 'UTC'
    #dbclient = db_client(request)
    dbclient = kwargs['db_key']
    cur = connections[dbclient].cursor()
    try:
        aux = AuxDataReport(cols=[], data=[], config={})
        cur.execute(result['sql'], result['pm'])
        aux.cols = [c.name for c in cur.description]

        for row in cur.fetchall():
            aux.data.append(row)
        cur.close()

        #CockpitCoreTools.HandleColumnNames(ref aux, parameters);
        
        return aux
    except Exception as e:
        raise e

def BuildQuery(request, parameters, kwargs):
    repHeader = GetReport(request, int(parameters["id"]), int(parameters["idBody"]))
    rep = repHeader['cellList']

    filters = []
    pm = dict()

    if not(parameters['isReport']):
        default_filters(parameters, repHeader, kwargs)

    SetupFilters(parameters, repHeader, filters, pm, kwargs)

    #user filter, if declared in sql
    if rep.ssql_rbd.upper().find("%(CODI_USU)s") >= 0 or [f for f in filters if f.upper().find("%(CODI_USU)s") > 0]:
        pm["CODI_USU"] = request.user.id 

    sql = ""
    if len(filters) > 0:
        listFilter = str.join(" and ", filters)
        sql = rep.ssql_rbd.replace("{0}", listFilter)

        pattern = re.compile(r'_except:([0-9]+,)*[0-9]+_')
        for match in re.finditer(pattern, sql):
            sGroup = match.group()
            cloned = filters.copy()
            indexes = [int(i) for i in sGroup.replace("_except:", "").replace("_", "").split(',')]
            for r in indexes:
                if cloned != None and len(cloned) > r:
                    cloned[r] = 'remove'
            left = [c for c in cloned if c != 'remove']
            sql = sql.replace(sGroup, str.join(" and ", left if len(left) > 0 else ["(1=1)"] ))
    else:
        sql = rep.ssql_rbd.replace("{0}", "(1=1)")
    type_c = rep.type_rbd
    return dict( sql=sql, pm=pm, type=type_c )

def view_types(div_type):
    mapTypes = [ "map", "staticmap", "accordionmap", "heatmap", "accordionheatmap" ]
    tableTypes = [ "table", "rowspantable", "clusteredtable" ]
    
    
    div_type_simple = div_type.replace("transposezerotwodigits", "").replace("transposezeropercent", "").replace("transposezero", "").replace("transposenull", "").replace("transpose", "")
    div_type_simple = re.sub("orderedby[0-9]+|numorderedby[0-9]+|descorderedby[0-9]+|descnumorderedby[0-9]+", "", div_type_simple)
    if div_type_simple.startswith("clusteredtable"):
        columns = [ int(x) for x in div_type_simple.replace("clusteredtable.", "").split('.') ]
        div_type_simple = div_type_simple.replace("clusteredtable.", "table").replace(str.join(".", [str(c) for c in columns ]  ), "")
    if div_type_simple.startswith("rowspantable"):
        columns = [ int(x) for x in div_type_simple.replace("rowspantable.", "").split('.') ]
        div_type_simple = div_type_simple.replace("rowspantable.", "table").replace(str.join(".", [str(c) for c in columns ]  ), "")
    
    if any([ div_type_simple.startswith(t) for t in tableTypes ]):
        return 'table'
    elif any([ div_type_simple.startswith(t) for t in mapTypes ]):
        return 'map'
    else:
        return div_type_simple

def default_filters(parameters, rep, kwargs):
    default_values = rep['report'].customreportconfig.para_rcf.split(";")
    definition = AutoCompleteMap.autocompletemap(None, kwargs)
    filters = rep['report'].filters(definition)

    for i, f in enumerate(filters):
        rawName = f.type
        if rawName in ["DATEBTW", "DATEYMBTW"]:
            from_to = get_datefilters()
            parameters['from'] = from_to[default_values[i]][2].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            parameters['to'] = from_to[default_values[i]][3].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        elif definition[rawName]:
            parameters[rawName] = default_values[i].split(",")

def SetupFilters(parameters, rep, filters, pm, kwargs):
    BetweenFilter = "( {0} between %(BTWFROM)s and %(BTWTO)s )"
    DateFilter = "( {0} = %(DATEYM)s )"
    DataFilter = "( {0} = %(BTWFROM)s )"

    INTERVAL_TEMPLATES = {
        "hours": ['HH24:00', 'DD HH24:00', '1 hour'],
        "week": ['DD/MM', 'YYYY-MM-DD', '1 day'], 
        "month": ['MM/YYYY', 'YYYY-MM', '1 month'], 
        "year": ['YYYY', 'YYYY', '1 year']
    }
    INTERVAL_TEMPLATES_2 = {
        "hours": ['HH24:MI', 'DD HH24:MI', '15 minutes'], 
        "week": ['DD/MM', 'YYYY-MM-DD', '1 day'], 
        "month": ['MM/YYYY', 'YYYY-MM', '1 month'], 
        "year": ['YYYY', 'YYYY', '1 year']
    }
    TRANSLATE = {"hours": 'Hora', "week": 'Dia', "month": 'Mês', "year": 'Ano'}

    definition = AutoCompleteMap.autocompletemap(None, kwargs)

    radioCount = 0
    checkboxCount = 0
    textFieldCount = 0
    plainFieldCount = 0
    selectCount = 0
    fsql_rbd = rep['cellList'].fsql_rbd.split(';')

    count_filters = 0
    for f in rep['report'].filters(definition):
        sql = fsql_rbd[count_filters]
        count_filters = count_filters + 1
        rawName = f.type
        if rawName == "DATEBTW":
            if not(parameters["from"]) or not(parameters["to"]):
                raise Exception(str.format("Filtro {0} não foi especificado.", f.label))
            if sql == "":
                filters.append("(1=1)")
            else:
                filters.append(str.format(BetweenFilter, sql, f.type))

            from_d = datetime.strptime(parameters['from'], '%Y-%m-%dT%H:%M:%S.%fZ') 
            to_d = datetime.strptime(parameters['to'], '%Y-%m-%dT%H:%M:%S.%fZ') 

            pm["BTWFROM"] = from_d
            pm["BTWTO"] = to_d

            pm["STARTYEAR_FROM"] = datetime(from_d.year, 1, 1)
            pm["STARTYEAR_TO"] = datetime(to_d.year, 1, 1)
            pm["STARTMONTH_TO"] = datetime(to_d.year, to_d.month, 1)
            pm["ENDMONTH_FROM"] = datetime(from_d.year, from_d.month, 1) + relativedelta(months=1) + timedelta(days=-1)
            pm["ENDMONTH_TO"] = datetime(to_d.year, to_d.month, 1) + relativedelta(months=1) + timedelta(days=-1)

            pm["YEAR_FROM"] = int(from_d.year)
            pm["MONTH_FROM"] = int(from_d.month)
            pm["YEAR_TO"] = int(to_d.year)
            pm["MONTH_TO"] = int(to_d.month)

            interval = interval_parameters(from_d, to_d)
            pm["date_format"] = INTERVAL_TEMPLATES[interval][0]
            pm["order"] = INTERVAL_TEMPLATES[interval][1]
            pm["step"] = INTERVAL_TEMPLATES[interval][2]
            pm["date_format2"] = INTERVAL_TEMPLATES_2[interval][0]
            pm["order2"] = INTERVAL_TEMPLATES_2[interval][1]
            pm["step2"] = INTERVAL_TEMPLATES_2[interval][2]
        elif rawName == "DATEYMBTW":
            if not(parameters["from"]) or not(parameters["to"]):
                raise Exception(str.format("Filtro {0} não foi especificado.", f.label))
            if sql == "":
                filters.append("(1=1)")
            else:
                filters.Add(str.format(BetweenFilter, sql, f.Type))

            from_d = datetime.strptime(parameters['from'], '%m/%d/%y %H:%M:%S') 
            to_d = datetime.strptime(parameters['to'], '%m/%d/%y %H:%M:%S') 
            
            pm["BTWFROM"] = from_d
            pm["BTWTO"] = to_d

            pm["STARTYEAR_FROM"] = datetime(from_d.year, 1, 1)
            pm["STARTYEAR_TO"] = datetime(to_d.year, 1, 1)
            pm["STARTMONTH_FROM"] = datetime(from_d.year, from_d.month, 1)
            pm["STARTMONTH_TO"] = datetime(to_d.year, to_d.month, 1)
            pm["ENDMONTH_FROM"] = datetime(from_d.year, from_d.month, 1) + relativedelta(months=1) + timedelta(days=-1)
            pm["ENDMONTH_TO"] = datetime(to_d.year, to_d.month, 1) + relativedelta(months=1) + timedelta(days=-1)

            pm["YEAR_FROM"] = int(from_d.year)
            pm["MONTH_FROM"] = int(from_d.month)
            pm["YEAR_TO"] = int(to_d.year)
            pm["MONTH_TO"] = int(to_d.month)

            interval = interval_parameters(from_d, to_d)
            pm["date_format"] = INTERVAL_TEMPLATES[interval][0]
            pm["order"] = INTERVAL_TEMPLATES[interval][1]
            pm["step"] = INTERVAL_TEMPLATES[interval][2]
            pm["date_format2"] = INTERVAL_TEMPLATES_2[interval][0]
            pm["order2"] = INTERVAL_TEMPLATES_2[interval][1]
            pm["step2"] = INTERVAL_TEMPLATES_2[interval][2]
        elif rawName == "DATEYM":
            if not(parameters["from"]):
                raise Exception(str.format("Filtro {0} não foi especificado.", f.label))
            if sql == "":
                filters.append("(1=1)")
            else:
                filters.append(str.format(DateFilter, sql, f.Type))

            from_d = datetime.strptime(parameters['from'], '%m/%d/%y %H:%M:%S') 

            pm["DATEYM"] = from_d

            pm["STARTYEAR_FROM"] = datetime(from_d.year, 1, 1)
            pm["STARTMONTH_FROM"] = datetime(from_d.year, from_d.month, 1)
            pm["ENDMONTH_FROM"] = datetime(from_d.year, from_d.month, 1) + relativedelta(months=1) + timedelta(days=-1)

            pm["YEAR_FROM"] = int(from_d.year)
            pm["MONTH_FROM"] = int(from_d.month)
        elif rawName == "DATA":
            if not(parameters["from"]):
                raise Exception(str.format("Filtro {0} não foi especificado.", f.label))
            filters.append(str.format(DataFilter, sql, f.Type))

            from_d = datetime.strptime(parameters['from'], '%m/%d/%y %H:%M:%S') 

            pm["BTWFROM"] = from_d

            pm["STARTYEAR_FROM"] = datetime(from_d.year, 1, 1)
            pm["STARTMONTH_FROM"] = datetime(from_d.year, from_d.month, 1)
            pm["ENDMONTH_FROM"] = datetime(from_d.year, from_d.month, 1) + relativedelta(months=1) + timedelta(days=-1)

            pm["YEAR_FROM"] = int(from_d.year)
            pm["MONTH_FROM"] = int(from_d.month)
        elif rawName=="TEXT":
            value = parameters["TEXT"][textFieldCount]
            if sql == "" or value.strip() == "":
                filters.append("(1=1)")
            else:
                filters.append(str.format("(  to_tsvector('portuguese', {0}) @@ to_tsquery('portuguese',{1}||':*') or {0} ilike {1}||'%' or {0} ilike '%'||{1}  )", sql, "text{0}".format(textFieldCount)))

            pm["text" + str(textFieldCount)] = ( value if value != "" else None)
            textFieldCount = textFieldCount + 1
        elif rawName in ["NINT32", "NINT64", "IINT32", "IINT64" ]:
            filters.append("(1=1)")
            value = parameters["PLAIN"][plainFieldCount]
            pm["plain%s"%(plainFieldCount)] = int(value) if value != "" else None
            plainFieldCount = plainFieldCount + 1
        elif rawName == "SELECT":
            if "SELECT" not in parameters:
                raise Exception(str.format("Filtro {0} não foi especificado.", f.label))
            filters.append("(1=1)")
            pm["select%s"%(selectCount)] = str(parameters[rawName][selectCount])
            selectCount = selectCount + 1
        elif rawName == "RADIO":
            if "RADIO" not in parameters:
                raise Exception(str.format("Filtro {0} não foi especificado.", f.label))
            filters.append("(1=1)")
            pm["radio%s"%(radioCount)] = str(parameters[rawName][radioCount])
            radioCount = radioCount + 1
        elif rawName == "CHECKBOX":
            if "CHECKBOX" not in parameters:
                raise Exception(str.format("Filtro {0} não foi especificado.", f.label))
            filters.append("(1=1)")
            pm["checkbox%s"%(checkboxCount)] = str(parameters[rawName][checkboxCount])
            checkboxCount = checkboxCount + 1
        elif definition[rawName]:
            if parameters[rawName]:
                def_val = definition[rawName]
                values = parameters[rawName]
                if def_val['key_type'] == "string":
                    SetupInFilter(filters, pm, f, sql, values)
                elif def_val['key_type'] == "int":
                    SetupInFilter(filters, pm, f, sql, [int(v) for v in values])
                elif def_val['key_type'] == "int[]":
                    SetupInFilter(filters, pm, f, sql, [int(v) for v in values], True)
                elif def_val['key_type'] == "string[]":
                    SetupInFilter(filters, pm, f, sql, values, True)
                # else: #tipo não especificado realizar testes até encontrar um tipo que possa ser utilizado
                #     if values.Count > 0:
                #         if values.TrueForAll(x => Regex.IsMatch(x, "[0-9]+", RegexOptions.CultureInvariant)): #Teste de Inteiros
                #             SetupInFilter(filters, pm, f, values.ConvertAll<Int32>(x => Convert.ToInt32(x)))
                #         else: #String como caso residual
                #             SetupInFilter(filters, pm, f, values)
            else:
                values = None
                # SetupInFilter(filters, pm, f, values)

def interval_parameters(date_start, date_end):
    if date_start > date_end:
        raise Exception('Invalid date interval!')

    diff = date_end - date_start
    if date_start.date() == date_end.date() or diff.days <= 1:
        return 'hours'
    elif diff.days > 1 and diff.days <= 45:
        return 'week'
    elif diff.days > 45 and diff.days <= ( 365 + 30 ):
        return 'month'
    else:
        return 'year'

def SetupInFilter(filters, pm, f, sql, items, isArray = False):
    InFilter = "({0} && array[{1}])" if isArray else "({0} in ({1}))"

    if items == None:
        filters.append("(1=1)")
        return

    if len(items) > 0:
        ins = str.join(',', ["%%(%s%s)s"%(f.type, i) for i in range(len(items))])
        filters.append(str.format(InFilter, sql, ins))
        for i in range(len(items)):
            pm["%s%s"%(f.type, i)] = items[i]

def rowspan_data(type, aux):
    position = 0
    columns = [ int(x) for x in type.replace("rowspantable.", "").split('.') ]
    columns.sort()
    
    rowspans = [ [ 0 for x in range(0, len(aux.data[0]) ) ] for i in range( 0, len(aux.data) ) ]
    spanNum = [0] * len(aux.data[0])
    # Tabela com rowspan
    for i in range(0, len(aux.data)):
        for j in range(0, len( aux.data[i] ) ):
            columnID = aux.cols[j].replace(" ", "_")
            if j in columns:
                if spanNum[j] == 0:
                    rangeConditions = columns[0: columns.index(j) + 1 ]  
                    rowspan = len( [ x for x in aux.data if all( x[y] == aux.data[i][y] for y in rangeConditions ) ] )
                    spanNum[j] = rowspan - 1
                    rowspans[i][j] = rowspan
                else:
                    spanNum[j] = spanNum[j] - 1
                    rowspans[i][j] = None
            else:
                rowspans[i][j] = 1
    aux.rowspan = rowspans
    return type.replace("rowspantable.", "table").replace(str.join(".", [str(c) for c in columns ]  ), "")


def cluster_data(type, aux):
    #Faz agrupamento de dados de uma tabela a fim de produzir tabelas dentro de tabelas
    # ou seja, ao clicar numa linha da tabela a linha expande mostrando subtabelas
    position = 0
    columns = [ int(x) for x in type.replace("clusteredtable.", "").split('.') ]
    columns.sort()
    columnsCluster = ( columns if len(columns) == 1 else columns[:-1] )
    numberOfRows = ( 1 if len(columns) == 1 else columns[-1] )
    emptyLines = [ [''] * len(aux.cols) ] * numberOfRows # Create bidimensional empty string array


    mirrorList = aux.data.copy()

    # aux.data.ToList().GroupBy(x => String.Join(".", columnsCluster.ToList().ConvertAll<String>(y => x[y]))).Select(group => new
    # {
    #     Metric = group.Key,
    #     Count = group.Count()
    # }).ToList().ForEach(x =>
    # {
    #     position += x.Count;
    #     mirrorList.InsertRange(position, emptyLines);
    #     position += emptyLines.Count;
    # })
    aux.data = mirrorList.copy()

    return type.replace("clusteredtable.", "table").replace(str.join(".", [str(c) for c in columns ]  ), "")

def GetReport(request, id, idBody = None, idBodyExtra = None):
    try:
        #dbclient = db_client(request)
        dbclient = 'default'
        reportList = CustomReport.objects.using(dbclient).filter(codi_rep = id)
        if len(reportList) == 0:
            raise Exception("Relatório não encontrado.")

        report = reportList[0]
        report_config = None
        customBodyCell = []

        if idBody != None:
            customBodyCell = report.customreportbody_set.get(codi_rbd = idBody)
        else:
            step = 0
            # Vefifica se existe configurações de gestão a vista no registro, senão é um relatório
            if hasattr(report, 'customreportconfig'):
                report_config = { 'freq': report.customreportconfig.freq_rcf, 'seeds': [] }
                if report.customreportconfig.stru_rcf and report.customreportconfig.stru_rcf.strip() != '':
                    conf_report = json.loads(report.customreportconfig.stru_rcf)
                    if 'sql' in conf_report:
                        cell_conf = []
                        height = int(conf_report['maxheight']) if 'maxheight' in conf_report else 5
                        seeds = Structure_Config( request, conf_report['sql'] )
                        for s in seeds:
                            cell = {'id': s['_id'] }
                            if 'template' in conf_report:
                                cell['template'] = conf_report['template'].replace('{{id}}', str(s['_id'])).replace('{{title}}', s['_title'])
                            if 'ordination' in conf_report:
                                if conf_report['ordination'].startswith('box'):
                                    ram = conf_report['ordination'].replace('box-', '').replace('box', '')
                                    ram = ( 2 if ram == '' else int(ram) )  
                                    cell['x'] = ( step % ram ) * (12 / ram)
                                    cell['y'] = height * math.floor( step / ram )
                                    cell['width'] = 12 / ram
                                    cell['height'] = height
                                else:
                                    cell['x'] = 0
                                    cell['y'] = step * 5
                                    cell['width'] = 12
                                    cell['height'] = 5

                            step = step + 1
                            cell_conf.append(cell)
                        report_config['seeds'] = cell_conf

                        if 'addContent' in conf_report:
                            report_config['addContent'] = conf_report['addContent']
            
            #Verifica se é necessário buscar a estrutura do corpo da custom_report_body
            if report_config is None or ( 'seeds' in report_config and len(report_config['seeds']) == 0 ):
                for c in report.customreportbody_set.all().order_by('codi_rbd'):
                    if c.ordr_rbd and c.ordr_rbd.strip() != '':
                        ordination = json.loads(c.ordr_rbd)
                        if 'x' in ordination and 'y' in ordination and 'width' in ordination and 'height' in ordination:
                            c.x = ordination['x']
                            c.y = ordination['y']
                            c.width = ordination['width']
                            c.height = ordination['height']
                        else:
                            c.x = 0
                            c.y = step * 5
                            c.width = 12
                            c.height = 5
                    step = step + 1

                    if c.type_rbd == 'table':
                        c.upperclass = 'grid-stack-item-content'
                        c.bottomclass = ''
                    else:
                        c.upperclass = ''
                        c.bottomclass = 'grid-stack-item-content'
                    customBodyCell.append(c)
            else:
                customBodyCell.extend([e for e in report.customreportbody_set.all().order_by('codi_rbd') ])

        return { 'report': report, 'config': report_config, 'cellList': customBodyCell }
    except Exception as e:
        print(e)
        raise e

def Structure_Config(request, sql):
    #timezone = get_timezone(request)
    timezone = 'UTC'
    #dbclient = db_client(request)
    dbclient = 'default'
    cur = connections[dbclient].cursor()
    try:
        data = []
        cur.execute(sql, [])

        desc = cur.description 
        data = [ dict(zip([col[0] for col in desc], row)) for row in cur.fetchall() ]
        cur.close()

        #CockpitCoreTools.HandleColumnNames(ref aux, parameters);
        
        return data
    except Exception as e:
        print(e)
        raise e
