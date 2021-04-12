import re
import json

from django.utils.translation import ugettext_lazy as _

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.http import HttpResponse

from django.shortcuts import render
from django.conf import settings
from django.db import connections
from django.http import JsonResponse

from app.tools.models import HelpTagItem
from app.tools.models import FavoriteReports
from app.tools.views_autocomplete import get_items
from app.customreport.models import CustomReport, CustomReportBody

from app.customreport.views import get_report_body
from common.general_operations import get_datefilters
from common.general_classes import AutoCompleteMap
from reposervice.decorators import extract_work, jwt_remote_authentication


from rest_framework import generics, response, status
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly, AllowAny, IsAuthenticated
from rest_framework_jwt.authentication import JSONWebTokenAuthentication
from rest_framework.mixins import ListModelMixin, UpdateModelMixin, RetrieveModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.parsers import FileUploadParser

class ReportHelpComponentEndpoint(APIView):
    @extract_work
    def post(self, request, *args, **kwargs):
        conf = {}
        conf['tags'] = [h.__dict__ for h in helptags_for(request, True, kwargs)]
        return HttpResponse(json.dumps(conf), content_type='application/json')

class ReportHelpIndexComponentEndpoint(APIView):
    @extract_work
    def post(self, request, *args, **kwargs):
        topic = request.data['topic'] if 'topic' in request.data else None
        if topic:
            supported = ['custom-report__' + str(r.codi_rep) for r in CustomReport.objects.all()]

            if topic not in supported:
                conf = { 'founded': False }
            else:
                request.data['type'] = 'report' if 'report' in topic else 'register'
                request.data['key'] = topic.replace('custom-report__', '').replace('custom-crud__', '')
                tags = [h.__dict__ for h in helptags_for(request, True, kwargs)]

                fields = []
                if request.data['type'] == 'register':
                    fields = [ [f.verbose_name, f.help_text]  for f in [s for s in supported if s[0] == topic][0][2]._meta.fields]
                                        
                conf = {
                    'header': [t for t in tags if t['group'] == 'Head'][0],
                    'filters': [t for t in tags if t['group'] == 'Filters'],
                    'body': [t for t in tags if t['group'] == 'Body'],
                    'type': request.data['type'], 
                    'tags': tags,
                    'fields': fields,
                    'options': supported,
                    'sample': sample_report(request, topic, kwargs) if 'custom-report__' in topic else dict(),
                    'request_type': 1,
                    'founded': True
                }

            return HttpResponse(json.dumps(conf), content_type='application/json')
        else:
            supported = [['custom-report__'+str(r.codi_rep), r.nome_rep, 'report'] for r in CustomReport.objects.all()]


            query = request.data['q'].lower()
            results = []
            for s in supported:
                request.data['type'] = s[2]
                request.data['key'] = s[0].replace('custom-report__', '')
                all_tags = helptags_for(request, True, kwargs)
                
                fields = ''
                # if len(s) > 2:
                #     fields = str.join('\n', [ "%s: %s"%(f.verbose_name, f.help_text)  for f in s[2]._meta.fields] )
                content = "%s\n%s"%( str.join('\n', ["%s %s %s"%( c.title, c.body, c.examples ) for c in all_tags] ), fields )
                result = re.findall(r'(%s)'%(query), content, re.IGNORECASE)
                if len(result) > 0:
                    results.append([s, len(result)])

            return HttpResponse(json.dumps({ 'results': results, 'options': supported, 'request_type': 2, 'founded': True }), content_type='application/json')

def sample_report(request, topic, kwargs):
    pk = topic.replace('custom-report__', '')
    header = CustomReport.objects.using('default').get(pk=pk)
    favorite = [f for f in FavoriteReports.objects.using('default').filter( form_id = pk ) ]
    if len(favorite) > 0:
        name = [ f.name for f in favorite if f.field_value == 'Últimos 12 Meses']
        if len(name) == 0:
            name = [ f.name for f in favorite if f.favorite_report_id == max([ f.favorite_report_id for f in favorite ]) ][0]
            favorite = [ f for f in favorite if f.name == name and f.field_name != 'url_path' ]
        else:
            favorite = [ f for f in favorite if f.name == name[0] and f.field_name != 'url_path']

    if len(favorite) == 0:
        return dict()

    parameters = { 'id': pk, 'isReport': True }
    entity_map = AutoCompleteMap.autocompletemap(None, kwargs)
    for h in header.filters(entity_map):
        fvr = [f for f in favorite if f.field_name == h.dom_id ]
        if len(fvr) > 0:
            f = fvr[0]
            if h.type == 'DATEBTW':
                from_to = get_datefilters()
                parameters['from'] = from_to[ f.field_value ][2].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                parameters['to'] = from_to[ f.field_value ][3].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            elif h.type in ['SELECT', 'RADIO', 'CHECKBOX']:
                if h.type not in parameters:
                    parameters[ h.type ] = []
                parameters[ h.type ].append( f.field_value  )
            elif h.is_autocomplete:
                parameters[ f.field_name.replace('select', '') ] = [ f.split(' **&& ')[1] for f in f.field_value.split(' ¶¶µµ ') ]
        elif h.type in ['SELECT', 'RADIO', 'CHECKBOX']:
            if h.type not in parameters:
                parameters[ h.type ] = []
            parameters[ h.type ].append(h.items[0][0])
        elif h.is_autocomplete:
            parameters[ h.dom_id.replace('select', '') ] = []

    outputs = {} 
    for b in [ b for b in header.customreportbody_set.all() ]:  
        if 'many' not in b.type_rbd:
            parameters['idBody'] = b.codi_rbd
            parameters['type'] = b.type_rbd
            outputs[b.codi_rbd] = get_report_body(request, parameters, kwargs).__dict__
            outputs[b.codi_rbd]['type'] = b.type_rbd
            outputs[b.codi_rbd]['toServer'] = parameters

    return outputs

def helptags_for(request, window_mode, kwargs=None):
    tags = []
    if request.data['type'] == 'report':
        header = CustomReport.objects.using('default').get(pk = int(request.data['key']) )
        
        #Help Filters
        tags.append( HelpTagItem(title=str(_(header.nome_rep)), body=str(_(header.desc_rep)), path='.page-title', group = 'Head') )
        entity_map = AutoCompleteMap.autocompletemap(None, kwargs)
        for f in header.filters(entity_map):
            if f.type == 'DATEBTW':
                tags.append(daterange(f.dom_id, f.label))
                tags.append(navigate_panel())
                tags.append(filter_wall())
            elif f.type in ['SELECT', 'RADIO', 'CHECKBOX']:
                tags.append( generic_selectors(f) )
            elif f.type in entity_map:
                tags.append(select(f.type, request, window_mode, f.obg, kwargs))

        #Help body
        bodies = sorted([ h for h in header.customreportbody_set.all() ], key=lambda x: x.codi_rbd)
        for b in bodies:
            tags.append( 
                HelpTagItem(
                    title=str(_(b.nome_rbd)), 
                    body=str(_(b.desc_rbd)), 
                    group= 'Body', 
                    path='#fieldset_%s .card-title'%(b.codi_rbd)
                )
            )
        
        return tags
    # elif link in [r[0] for r in supported_crud()]:
    #     return get_ctags(request, window_mode, link)
    return tags

# region Report Methods
def daterange(dom_id, label):
    return HelpTagItem(
        path='#'+dom_id,
        title= label if label else 'Período',
        body=str( ('''Este filtro é responsável por determinar um intervalo de tempo de requisição. O intervalo
        considerado é inclusivo, o que significa que incluirá a data de início e a data de término definidas no
        termos de pesquisa.
        Este filtro é obrigatório. A data de início deve ser anterior à data de término.
        ''') ),
        group= 'Filters'
    )

def navigate_panel():
    return HelpTagItem(
        title=str(_('Botões de Navegação')), 
        body=str(_('''02 (dois) botões que alteram a data da pesquisa atual.''')), 
        path='#rewind',
        group= 'Component',
        position='TR'
    )

def filter_wall():
    return HelpTagItem(
        title=str(_('Painel de Fitros')), 
        body=str(_('''Neste componente é possível buscar configurações de consultas realizados previamente nesse relatório''')), 
        path='#report_wall',
        group= 'Component',
        position='BL'
    )

def generic_selectors(f):
    if f.type == 'SELECT':
        sel = 'lista de opções'
        qnt = 'uma única opção'
    elif f.type == 'RADIO':
        sel = 'radio button'
        qnt = 'uma única opção'
    elif f.type == 'CHECKBOX':
        sel = 'checkbox'
        qnt = 'uma ou mais opções'

    items = str.join(', ', [ i[0] for i in  f.items ] )
    return HelpTagItem(
        title=str(_(f.label)), 
        body=str( _('Filtro do tipo %s usado para selecionar %s opções dentre a lista das seguintes opções: %s'%(sel,qnt, items) )), 
        group= 'Filters',
        path='#'+f.dom_id
    )

def select(entity, request, has_sample=False, is_obg=False, kwargs=None):
    select_entity = AutoCompleteMap.autocompletemap(entity, kwargs)
    title = str(_(select_entity['label']))
    body = str(_(select_entity['description']))

    sample = None
    if has_sample:
        sample = [e['text'] for e in get_items(entity, None, {}, True, request, kwargs)['results']]

    return HelpTagItem(
        title=title, 
        body=body, 
        group= 'Filters', 
        examples=sample, 
        path='#div_select%s'%(entity)
    )
# endregion