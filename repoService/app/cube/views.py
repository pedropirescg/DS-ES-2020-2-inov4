import csv
import json
import xlwt as xlwt

#TODO Atualizar com db_client
#from apps.core.views import db_client, get_timezone
from django.db import connections
from django.http import JsonResponse
from django.http import HttpResponse
from django.shortcuts import render
from datetime import datetime
# from mvp_project.settings.settings import LOGIN_REDIRECT_URL
# from django.contrib.auth.decorators import login_required

from reposervice.decorators import extract_work, jwt_remote_authentication

from common.general_classes import ConfigQuery
from common.dynamic_query import GetPivotData
from common.dynamic_pivot  import DynamicPivot

from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly, AllowAny, IsAuthenticated
from rest_framework import generics, response, status
from rest_framework.views import APIView


class GetCubeEndpoint(APIView):
    @extract_work
    def get(self, request, *args, **kwargs):
        entity = DynamicPivot.EntityConfig(kwargs)
        total_metrics = {**entity['metricQuery'], **DynamicPivot.UtilityMetrics(kwargs)}

        filters = [d for d in entity['filterQuery']]
        dimensions = [[d, entity['dimensionQuery'][d]['label']] for d in entity['dimensionQuery']]
        metrics = [[d, total_metrics[d]['label'] ] for d in total_metrics if total_metrics[d]['conf'][2] ]
        m_map = { d: total_metrics[d]['granularity'] if 'granularity' in total_metrics[d] else [] 
            for d in total_metrics if total_metrics[d]['conf'][2] }
        config = [[d, total_metrics[d]['label'], total_metrics[d]['conf']] for d in total_metrics]
        config = json.dumps(config)

        params = {
            'filters': filters, 
            'dimensions': dimensions, 
            'metrics': metrics, 
            'm_map': m_map,
            'config': config
        }

        return HttpResponse(json.dumps(params), content_type='application/json')

class GetCubeDataEndpoint(APIView):
    @extract_work
    def post(self, request, *args, **kwargs):
        params = json.loads( request.data['content'] )
        params['date_start'] = datetime.strptime(params['dateStart'], '%Y-%m-%dT%H:%M:%S.%f')
        params['date_end'] = datetime.strptime(params['dateEnd'], '%Y-%m-%dT%H:%M:%S.%f')
        config = ConfigQuery(
            datetime.strptime(params['dateStart'], '%Y-%m-%dT%H:%M:%S.%f'),
            datetime.strptime(params['dateEnd'], '%Y-%m-%dT%H:%M:%S.%f'),
            params['Dimensions'],
            params['Metrics'],
            params['Filters']
        )
        
        result = GetPivotData(config, request, kwargs)

        return JsonResponse(json.dumps(result), safe=False)