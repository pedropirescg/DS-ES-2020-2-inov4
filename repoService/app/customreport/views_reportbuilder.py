import re
import json
import csv
import xlwt as xlwt
import base64
from PIL import Image
from io import BytesIO

#TODO Atualizar com db_client
#from app.core.views import db_client, get_timezone
from django.db import connections
from django.http import JsonResponse
from django.http import HttpResponse
from django.shortcuts import render

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
# from mvp_project.settings.settings import LOGIN_REDIRECT_URL
# from django.contrib.auth.decorators import login_required

from reposervice.decorators import extract_work, jwt_remote_authentication
from app.customreport.models import CustomReport, CustomReportBody, AuxDataReport

from common.general_classes import AutoCompleteMap
from common.matrix_operations import transpose_matrix
from common.dynamic_query import GetPivotQuery
from common.dynamic_pivot  import DynamicPivot

from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly, AllowAny, IsAuthenticated
from rest_framework import generics, response, status
from rest_framework.views import APIView

class GetReportBuilderEndpoint(APIView):
    # @login_required(login_url=LOGIN_REDIRECT_URL)
    # def get_report_builder(request):
    @extract_work
    def get(self, request, *args, **kwargs):
        entity = DynamicPivot.EntityConfig(kwargs)
        total_metrics = {**entity['metricQuery'], **DynamicPivot.UtilityMetrics(kwargs)}
        mapping = AutoCompleteMap.autocompletemap(None, kwargs)

        #db_client = db_client(request)
        db_client = 'default'
        user_id = kwargs['user_id'] #request.user.id

        filters = [{'label': str(mapping[d]['label']), 'id': d}
                for d in entity['filterQuery']]
        dimensions = [[d, entity['dimensionQuery'][d]['label']]
                    for d in entity['dimensionQuery']]
        metrics = [[d, total_metrics[d]['label']]
                for d in total_metrics if total_metrics[d]['conf'][2] ]
        m_map = { d: total_metrics[d]['granularity'] if 'granularity' in total_metrics[d] else [] 
            for d in total_metrics if total_metrics[d]['conf'][2] }
        config = [[d, total_metrics[d]['label'], total_metrics[d]['conf']]
                for d in total_metrics]
        config = json.dumps(config)

        report_list = [{'codi_rep': c.codi_rep, 'nome_rep': c.nome_rep, 'fgrp_rep': c.fgrp_rep} 
            for c in CustomReport.objects.using(db_client).filter(codi_usu=user_id) if c.report_db == kwargs['db_key']]
        result = {
            'report_list' : report_list, 
            'filters': filters, 
            'dimensions': dimensions, 
            'metrics': metrics, 
            'm_map': m_map,
            'config': config, 
            'range': [r for r in range(1,100)] 
        }
        
        return HttpResponse(json.dumps(result), content_type='application/json')

class GetReportBuilderSaveEndpoint(APIView):
    # @login_required(login_url=LOGIN_REDIRECT_URL)
    # def save_report(request):
    @extract_work
    def post(self, request, *args, **kwargs): 
        try:
            mapping = AutoCompleteMap.autocompletemap(None, kwargs)
            entity = DynamicPivot.EntityConfig(kwargs)
            parameters = json.loads(request.data['content'])

            #db_client = db_client(request)
            db_client = 'default'
            user_id = kwargs['user_id'] 
            dateColumn = entity['generalConfig']['dateColumn'] if 'dateColumn' in entity['generalConfig'] else 'datetime_read'

            codi_rep = parameters['codi_rep']
            if not(codi_rep) or codi_rep.strip() == '':
                codi_rep = 5000000
                while len( CustomReport.objects.using(db_client).filter(codi_rep=codi_rep) ) != 0:
                    codi_rep = max(5000000, CustomReport.objects.using(db_client).all().order_by("-codi_rep")[0].codi_rep + 1)
                
                header = CustomReport()
                header.codi_rep = codi_rep
                header.nome_rep = parameters['nome_rep']
                header.desc_rep = parameters['desc_rep']
                header.flab_rep = str.join(';', [ ('Período' if p['id'] == 'DATEBTW' else str(mapping[ p['id'] ]['label']) ) for p in parameters['filters'] ])
                header.ftyp_rep = str.join(';', [  "%s:%s%s"%(p['id'], p['required'], ':%s'%(p['limit']) if p['limit'] != 'ilimitado' else '')
                    if p['id'] != 'DATEBTW' else  'DATEBTW' for p in parameters['filters'] ]) 
                header.fgrp_rep = 'Meus Relatórios' 
                header.codi_usu = user_id
                header.report_db = kwargs['db_key']
                header.save(using=db_client)
            else:        
                affected = ( 
                    CustomReport.objects.using(db_client).filter(pk=int(codi_rep)).update(
                        nome_rep = parameters['nome_rep'],
                        desc_rep = parameters['desc_rep'],
                        flab_rep = str.join(';', [ ('Período' if p['id'] == 'DATEBTW' else str(mapping[ p['id'] ]['label']) ) for p in parameters['filters'] ]),
                        ftyp_rep = str.join(';', [  "%s:%s%s"%(p['id'], p['required'], ':%s'%(p['limit']) if p['limit'] != 'ilimitado' else '')
                            if p['id'] != 'DATEBTW' else  'DATEBTW' for p in parameters['filters'] ]),
                        fgrp_rep = 'Meus Relatórios',
                        codi_usu = user_id,
                        report_db = kwargs['db_key']
                    )
                )
                header = CustomReport.objects.using(db_client).get(pk = int(codi_rep))    

            #Deleta registros de componentes anteriores
            for b in header.customreportbody_set.all():
                b.delete()

            count = 1
            for b in parameters['components']:
                codi_rbd = 5000000 + count
                while len( CustomReportBody.objects.using(db_client).filter(codi_rbd=codi_rbd) ) != 0:
                    codi_rbd = max(5000000, CustomReportBody.objects.using(db_client).all().order_by("-codi_rbd")[0].codi_rbd + 1)

                b['filters'] = [dict(key= i.split(':')[0], values= ['1']) for i in header.ftyp_rep.split(';') if i.split(':')[0] != 'DATEBTW']
                
                body = CustomReportBody()
                body.codi_rbd = codi_rbd
                body.codi_rep = header
                body.nome_rbd = b['name']
                body.type_rbd = b['type']
                body.fsql_rbd = str.join(';', [ entity['filterQuery'][p['id']]['element'] if p['id'] != 'DATEBTW' else 'a.' + dateColumn for p in parameters['filters'] ]) 
                body.ordr_rbd = json.dumps(dict(x=int(b['x']), y=int(b['y']), width=int(b['width']), height=int(b['height'])))
                body.ssql_rbd = GetPivotQuery(b, request, kwargs)

                body.conf_rbd = json.dumps({
                    'titleX': str.join('-', [l['label'] for l in b['xAxis']] ) if b['type'] == 'table' else '',
                    'xAxis': str.join('<sep_axis>', ['%s:%s'%(e['id'],e['label']) for e in b['xAxis']]),
                    'yAxis': str.join('<sep_axis>', ['%s:%s'%(e['id'],e['label']) for e in b['yAxis']]),
                    'formatter': str.join(',', ['default2' for e in b['yAxis']])
                }, ensure_ascii=False, indent=4)

                body.save(using=db_client)
                count = count + 1

            # return JsonResponse({'id': header.codi_rep})
            result = {'id': header.codi_rep}
            return HttpResponse(json.dumps(result), content_type='application/json')
        except Exception as e:
            print(e)
            raise e 

class GetReportBuilderSearchEndpoint(APIView):
    # @login_required(login_url=LOGIN_REDIRECT_URL)
    # def search_report(request):
    @extract_work
    def post(self, request, *args, **kwargs): 
        codi_rep = int( request.data['codi_rep'] )

        db_client = 'default'
        user_id = kwargs['user_id']

        header = CustomReport.objects.using(db_client).get(codi_rep=codi_rep)
        return JsonResponse({
            'codi_rep': header.codi_rep,
            'nome_rep': header.nome_rep,
            'desc_rep': header.desc_rep,
            'filters': [h.split(':') for h in header.ftyp_rep.split(';')],
            'components': [{
                'nome_rbd': b.nome_rbd,
                'desc_rbd': b.desc_rbd,
                'ordr_rbd': b.ordr_rbd,
                'type_rbd': b.type_rbd,
                'xAxis': json.loads(b.conf_rbd)['xAxis'],
                'yAxis': json.loads(b.conf_rbd)['yAxis']
            } for b in header.customreportbody_set.all()],
        })

class GetReportBuilderDeleteEndpoint(APIView):
    # @login_required(login_url=LOGIN_REDIRECT_URL)
    # def delete_report(request):
    @extract_work
    def post(self, request, *args, **kwargs): 
        codi_rep = int( request.data['codi_rep'] )

        #db_client = db_client(request)
        db_client = 'default'
        user_id = kwargs['user_id'] #request.user.id

        header = CustomReport.objects.using(db_client).get(codi_rep=codi_rep)

        for b in header.customreportbody_set.all():
            b.delete()

        header.delete()

        result = {'status': True}
        return HttpResponse(json.dumps(result), content_type='application/json')
