import xlwt as xlwt
import re
import csv
import json

from reposervice.decorators import extract_work, jwt_remote_authentication

from datetime import datetime
# from apps.core.views import db_client, get_timezone
from django.conf import settings
from django.db import connections
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
from app.tools.models import FavoriteReports

from app.customreport.models import CustomReport
from common.general_operations import get_datefilters
from common.dynamic_pivot  import DynamicPivot
from common.general_classes import AutoCompleteMap

from app.tools.views_autocomplete import get_items

from rest_framework import generics, response, status
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly, AllowAny, IsAuthenticated
from rest_framework_jwt.authentication import JSONWebTokenAuthentication
from rest_framework.mixins import ListModelMixin, UpdateModelMixin, RetrieveModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.parsers import FileUploadParser

# region Component

class GetFilterWallComponentEndpoint(APIView):
    #def report_list(context, key, event, callback=None, compact=False):
    @extract_work
    def post(self, request, *args, **kwargs):
        conf = {}
        key = request.data['key'] 
        compact = request.data['compact']
        event = request.data['event']
        callback = request.data['callback']

        db_client = 'default'
        user_id = kwargs['user_id']
        report_db = kwargs['db_key']


        conf['id'] = "reportwall%s" % (key.replace(' ', '_'))
        conf['formcode'] = "%s" % (key.replace(' ', '_'))
        conf['plain_text'] = "%s" % (key)
        conf['compact'] = compact
        conf['applyID'] = event
        conf['callback'] = callback if callback else 'null'
        filters = [[r.name, r.field_value] for r in FavoriteReports.objects.using(db_client).filter(user_id = user_id, report_db=report_db, form_id=conf['formcode'], field_name= 'url_path').order_by('favorite_report_id')]
        if not(compact) and len(filters) == 0: # Filtro de valores default pré-cadastrado
            default_filters(conf['formcode'], user_id, report_db, request, kwargs)
            filters = [[r.name, r.field_value] for r in FavoriteReports.objects.using(db_client).filter(user_id = user_id, report_db=report_db, form_id=conf['formcode'], field_name= 'url_path').order_by('favorite_report_id')]
        
        conf['filters'] = filters

        return HttpResponse(json.dumps(conf), content_type='application/json')

# endregion 

class GetFilterInsertEndpoint(APIView):
    #def insert_filter(request):
    @extract_work
    def post(self, request, *args, **kwargs):
        db_client = 'default'
        filterName = request.data['saveFilterFilterName']
        formCode = request.data['saveFilterFormCode']
        form = [r for r in request.data if r not in ['csrfmiddlewaretoken', 'saveFilterFilterName', 'saveFilterFormCode']]
        for key in form:
            try:
                rel = FavoriteReports(
                    name=filterName,
                    field_value=request.data[key],
                    field_name=key,
                    form_id=formCode,
                    user_id= kwargs['user_id'],
                    report_db = kwargs['db_key']
                )
                rel.save(using=db_client)
            except Exception as inst:
                print("ERRO")

        return HttpResponse( json.dumps( { 'msg': 'Inserido com sucesso' } ) )

class GetFilterListFieldsEndpoint(APIView):
    #@login_required(login_url=LOGIN_REDIRECT_URL)
    #def get_filters(request):
    @extract_work
    def post(self, request, *args, **kwargs):
        db_client = 'default'
        filterName = request.data['filterName']
        formcode = request.data['formCode']
        cur_user = kwargs['user_id'] #request.user.id
        report_db = kwargs['db_key']

        result = FavoriteReports.objects.using(db_client).filter(report_db=report_db, user_id = cur_user, form_id = formcode, name = filterName)

        return HttpResponse(json.dumps( [[r.field_name, r.field_value] for r in result] ), content_type='application/json' )

class GetFilterDeleteEndpoint(APIView):
    #def delete_filters(request):
    @extract_work
    def post(self, request, *args, **kwargs):
        try:
            db_client = 'default'
            filterName = request.data['filterName']
            formcode = request.data['formCode']
            cur_user = kwargs['user_id']
            report_db = kwargs['db_key']

            result = FavoriteReports.objects.using(db_client).filter(report_db=report_db, user_id = cur_user, form_id = formcode, name = filterName).delete()
            return HttpResponse( json.dumps( {'response': True} ) )
        except Exception as e:
            print(e)
            return HttpResponse( json.dumps( {'response': False} ) )

def default_filters(formcode, user_id, report_db, request, kwargs):
    try:
        db_client = 'default'
        periods = [ k for k in get_datefilters().keys() ]

        with transaction.atomic():
            if formcode == 'Cube': # É um cubo de dados
                mapped = DynamicPivot.EntityConfig(kwargs)
                metrics = {**mapped['metricQuery'], **DynamicPivot.UtilityMetrics(kwargs)}
                dimensions = mapped['dimensionQuery']
                if len(metrics.keys()) > 0 and len(dimensions.keys()):
                    #Tenta selecionar pelo menos 2 métricas
                    source = sorted( list(set( [ metrics[x]['source'] for x in metrics ] )) )
                    s_metrics = [s for s in metrics if metrics[s]['source'] == source[0]]
                    s_metrics = s_metrics[ 0: min(2, len(s_metrics)) ]
                    # Tenta selecionar pelo menos duas dimensões
                    s_dimensions = [d for d in dimensions]
                    for m in s_metrics:
                        if 'excludeDimension' in metrics[m]:
                            s_dimensions = [d for d in s_dimensions if d not in metrics[m]['excludeDimension'] ]
                    s_dimensions = s_dimensions[ 0: min(3, len(s_dimensions) ) ]
                    if len(s_metrics) > 0 and len(s_dimensions):
                        name_favorite = str.join(' x ', [metrics[s]['label'] for s in s_metrics])
                        dimension_line = str.join(' ¶¶µµ ', [ dimensions[d]['label'] + ' **&& ' + d for d in s_dimensions ] )
                        for p in periods:
                            FavoriteReports.objects.using(db_client).create(report_db = report_db, user_id=user_id, form_id=formcode, name="%s - %s"%(name_favorite, p), field_name = 'date-interval', field_value = p )
                            FavoriteReports.objects.using(db_client).create(report_db = report_db, user_id=user_id, form_id=formcode, name="%s - %s"%(name_favorite, p), field_name = 'dim_lines', field_value = dimension_line )
                            FavoriteReports.objects.using(db_client).create(report_db = report_db, user_id=user_id, form_id=formcode, name="%s - %s"%(name_favorite, p), field_name = 'url_path', field_value = '/cube' )
                            for s in s_metrics:
                                FavoriteReports.objects.using(db_client).create(report_db = report_db, user_id=user_id, form_id=formcode, name="%s - %s"%(name_favorite, p), field_name = 'm_' + s, field_value = 'm_' + s )
            else: # É um customreport
                entity_map = AutoCompleteMap.autocompletemap(None, kwargs)
                report = CustomReport.objects.using(db_client).get(codi_rep = int(formcode))
                fields = report.filters(entity_map)
                has_time = len([ f for f in fields if f.dom_id == 'date-interval' ]) > 0
                obg_auto = [ f for f in fields if f.obg and f.is_autocomplete ]
                obg_not_auto = [ f for f in fields if f.obg and not(f.is_autocomplete) ]

                conf = []
                if has_time: # Data é o elemento de diversificação principal
                    conf = [{ 'date-interval' :p, 'name': "%s - %s"%(report.nome_rep, p) } for p in periods]
                
                if len(obg_auto) > 0:
                    auto_dict = { o.dom_id : get_items(o.type, '', [], True, request, kwargs)  for o in obg_auto }
                    auto_empty = [ a for a in auto_dict.keys() if int(auto_dict[a]['total']) == 0 ]
                    if len(auto_empty) > 0: # Existe um filtro autocomplete obrigatório com tabela vázia no BD
                        return
                    elif has_time:  # Todos os filtros autocompletáveis obrigatórios tem pelo menos 1 no BD e possui filtro de data
                        conf = [ {**c, **{ k: ('%s **&& %s')%( auto_dict[k]['results'][0]['text'], auto_dict[k]['results'][0]['id'] ) 
                            for k in auto_dict.keys() } } for c in conf ]
                    else: # Todos os filtros autocompletáveis obrigatórios tem pelo menos 1 no BD, não possui filtro de data -> 1 autocomplete será escolhido para diversificação
                        total_max = max( [int(auto_dict[k]['total']) for k in auto_dict.keys()] )
                        selected = [ k for k in auto_dict.keys() if int(auto_dict[k]['total']) == total_max ][0]
                        not_selected = [k for k in auto_dict.keys() if k != selected]

                        conf = []
                        items = auto_dict[selected]['results']
                        for i in items:
                            title = [ [ entity_map[selected.replace('select', '')]['label'] , i] ]
                            selected_vals = { selected.replace('select', ''): i['id'] }
                            filters = { selected: ('%s **&& %s')%( i['text'], i['id'] ), 'name': report.nome_rep }
                            for k in not_selected: # Constroi filtros obrigatórios com dependências
                                key = k.replace('select', '')
                                curr = entity_map[key]
                                depends = [ [s, [selected_vals[s]] ] for s in selected_vals if s in curr['depends'] ]
                                filtered_values = get_items(key, '', depends, True, request, kwargs)
                                if len(filtered_values) > 0:
                                    selected_vals.update({ key : filtered_values['results'][0]['id'] })
                                    x = filtered_values['results'][0]
                                    title.append( [curr['label'], x] )
                                    filters.update({ 'select' + key : ('%s **&& %s')%( x['text'], x['id'] ) })
                                else: # Configuração inválida por inexistência de combinação com filtros dependentes
                                    return
                            filters['name'] = filters['name'] + ' - ' + str.join( ', ', [t[0] + ': ' + t[1]['text']  for t in title ])
                            conf.append(filters)
                
                if len(obg_not_auto) > 0:
                    simple_field_dict = { o.dom_id: (o.items[0][0] if len(o.items) > 0 else 100 ) for o in obg_not_auto }
                    if has_time or len(obg_auto) > 0: # Algum filtro foi escolhido como diversificador (data ou autocompletável)
                        conf = [{**c, **simple_field_dict} for c in conf ]
                    else: #Nenhum filtro anterior foi selecionado como diversificador
                        total_max = max([len(o.items) for o in obg_not_auto])
                        if total_max == 0: # Todos os obrigatórios não autocompletáveis são input text ou number
                            selected = obg_not_auto[0].dom_id
                            label = obg_not_auto[0].label
                            items = [[10,10], [20,20], [30,30], [40,40], [50,50], [60,60], [70,70], [80,80], [90,90], [100,100]]
                        else: # Pelo menos um dos obrigatórios não autocompletáveis é um checkbox, radio ou select
                            aux = [k for k in obg_not_auto if len(k.items) == total_max ][0]
                            selected = aux.dom_id
                            label = aux.label
                            items = aux.items

                        del simple_field_dict[selected]
                        conf = [{**simple_field_dict.copy(), **( {selected: i[0], 'name': ('%s - %s:%s')%(report.nome_rep, label, (i[1] if len(i) == 2 else i[0]) ) } ) } for i in items]
                
                for c in conf:
                    FavoriteReports.objects.using(db_client).create(report_db = report_db, user_id=user_id, form_id=formcode, name=c['name'], field_name = 'url_path', field_value = ('/custom-report/' + formcode) )
                    for k in [l for l in c.keys() if l != 'name']:
                        FavoriteReports.objects.using(db_client).create(report_db = report_db, user_id=user_id, form_id=formcode, name=c['name'], field_name = k, field_value = c[k] )

    except Exception as e:
        print(e.__cause__)
        return