import re
import json
import math
import csv
import xlwt as xlwt
import base64
from PIL import Image
from io import BytesIO

# from apps.core.views import db_client, get_timezone
from django.db import connections
from django.http import JsonResponse
from django.http import HttpResponse
from django.shortcuts import render
from common.general_classes import AutoCompleteMap
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
# from mvp_project.settings.settings import LOGIN_REDIRECT_URL
# from django.contrib.auth.decorators import login_required

from common.general_operations import get_datefilters
from common.matrix_operations import transpose_matrix
from app.customreport.models import CustomCRUD

from reposervice.decorators import extract_work, jwt_remote_authentication


from rest_framework import generics, response, status
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly, AllowAny, IsAuthenticated
from rest_framework_jwt.authentication import JSONWebTokenAuthentication
from rest_framework.mixins import ListModelMixin, UpdateModelMixin, RetrieveModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.parsers import FileUploadParser

def dumper(obj):
    try:
        return obj.toJSON()
    except:
        return obj.__dict__

class CRUDEndpoint(APIView):
    @extract_work
    # def views_crud(request, id):
    def get(self, request, *args, **kwargs):
        #dbclient = db_client(context.request)
        dbclient = 'default'

        id = kwargs['id']
        crud = dict()
        entity_map = AutoCompleteMap.autocompletemap(None, kwargs)
        ref_crud = CustomCRUD.objects.using(dbclient).get(codi_crd = id)
        crud['crud'] = { 'codi_crd': ref_crud.codi_crd, 'nome_crd': ref_crud.nome_crd, 'fgrp_crd': ref_crud.fgrp_crd }
        crud['config'] = json.loads( ref_crud.conf_crd )
        crud['filters'] = [k for k in entity_map]
        crud['fields'] = ref_crud.filters(entity_map)
        crud['valid'] = [{'label': f.label, 'id': f.dom_id} for f in crud['fields'] if f.obg]
        # return render(request, "crud_template.html", crud)
        return HttpResponse(json.dumps(crud, default=dumper), content_type='application/json')

class CRUDSearchEndpoint(APIView):
    @extract_work
    #def search_entity(request):
    def post(self, request, *args, **kwargs):
        codi = int( request.data['id'] )
        crud = CustomCRUD.objects.using('default').get(codi_crd = codi)
        # timezone = get_timezone(request)
        # dbclient = db_client(request)
        timezone = 'UTC'
        dbclient = kwargs['db_key']
        cur = connections[dbclient].cursor()
        try:
            pm = dict()
            configs = json.loads( crud.conf_crd )
            fields = ( configs['id'] + ', ' if 'id' in configs else '' ) + str.join(', ', crud.ftab_crd.split(';') )
            result = 'select %s from %s'%( fields , crud.tabl_crd )

            if 'pkey' in request.data:
                pkey = request.data['pkey']
                result += ' where ' + configs['id'] + ' = %(pkey)s' 
                pm['pkey'] = pkey

            cur.execute(result, pm) 

            entity_map = AutoCompleteMap.autocompletemap(None, kwargs)
            cols = [c.dom_id for c in crud.filters(entity_map)]
            data = [ CRUDSearchEndpoint.convert_row(row) for row in cur.fetchall() ]
            cur.close()
            
            return JsonResponse({ 'data':data, 'cols': cols }, safe=False)
        except Exception as e:
            print(e)
            raise e

    @staticmethod
    def convert_row(row):
        new_row = []
        for r in row:
            if type(r) is datetime:
                new_row.append(r.strftime("%d/%m/%Y %H:%M"))
            else:
                new_row.append(r)
        return new_row

class CRUDSaveEndpoint(APIView):
    @extract_work
    # def save_entity(request):
    def post(self, request, *args, **kwargs):
        codi = int( request.data['id'] )
        values = json.loads(request.data['content'])
        crud = CustomCRUD.objects.using('default').get(codi_crd = codi)
        # timezone = get_timezone(request)
        # dbclient = db_client(request)
        timezone = 'UTC'
        dbclient = kwargs['db_key']
        cur = connections[dbclient].cursor()
        try:
            pm = dict()
            configs = json.loads( crud.conf_crd )        

            pkey = request.data['pkey'] if 'pkey' in request.data else ''
            if pkey == '':
                fields = str.join(', ', crud.ftab_crd.split(';') )
                val_str = str.join(',', ['%%(%s)s'%(f) for f in crud.ftab_crd.split(';')])
                result = 'insert into %s(%s) \nvalues( %s )'%( crud.tabl_crd, fields, val_str )           
            else:
                val_str = str.join(',', ['\n%s = %%(%s)s'%(f,f) for f in crud.ftab_crd.split(';')])
                result = 'update %s set %s '%( crud.tabl_crd, val_str )
                result += '\nwhere ' + configs['id'] + ' = %(pkey)s'
                pm['pkey'] = pkey

            entity_map = AutoCompleteMap.autocompletemap(None, kwargs)
            dom = [ [f.dom_id, f.type] for f in crud.filters(entity_map) ]
            for key, value in enumerate(crud.ftab_crd.split(';')):
                if dom[key][1] == 'FLOAT':
                    pm[value] = float(values[ dom[key][0] ])
                elif dom[key][1] == 'DATA':
                    pm[value] = datetime.strptime(values[ dom[key][0] ], '%d/%m/%Y %H:%M')
                else:
                    pm[value] = values[ dom[key][0] ]

            cur.execute(result, pm) 
            cur.close()
            
            return JsonResponse({ 'data':'sucess' }, safe=False)
        except Exception as e:
            print(e)
            raise e

class CRUDDeleteEndpoint(APIView):
    @extract_work
    # def delete_entity(request):
    def post(self, request, *args, **kwargs):
        codi = int( request.data['id'] )
        crud = CustomCRUD.objects.using('default').get(codi_crd = codi)
        # timezone = get_timezone(request)
        # dbclient = db_client(request)
        timezone = 'UTC'
        dbclient = kwargs['db_key']
        cur = connections[dbclient].cursor()
        try:
            pm = dict()
            configs = json.loads( crud.conf_crd )
            result = 'delete from %s'%( crud.tabl_crd )

            pkey = request.data['pkey']
            if pkey:
                result += ' where ' + configs['id'] + ' = %(pkey)s' 
                pm['pkey'] = pkey

            cur.execute(result, pm) 
            cur.close()
            
            return JsonResponse({ 'data':'sucess' }, safe=False)
        except Exception as e:
            print(e)
            raise e
