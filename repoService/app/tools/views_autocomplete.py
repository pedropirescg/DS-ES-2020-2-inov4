import re

from django.shortcuts import render
from django.conf import settings
from django.db import connections
from django.http import JsonResponse

from common.general_classes import AutoCompleteMap
from reposervice.decorators import extract_work, jwt_remote_authentication


from rest_framework import generics, response, status
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly, AllowAny, IsAuthenticated
from rest_framework_jwt.authentication import JSONWebTokenAuthentication
from rest_framework.mixins import ListModelMixin, UpdateModelMixin, RetrieveModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.parsers import FileUploadParser

def get_items(key, text, depends, sample, request, kwargs):
    #timezone = get_timezone(request)
    timezone = 'UTC'
    columnName = []
    result_query = []
    #dbclient = db_client(request)
    dbclient = kwargs['db_key']
    cur = connections[dbclient].cursor()
    try:
        result = generate_query(key, ( text and text != '' ), sample, depends, kwargs)
        parameters = result[1]
        parameters.update({'term': text})

        set_timezone = "SET TIMEZONE = '{}';".format(timezone)
        query = "{} {}".format(set_timezone, result[0])

        cur.execute(query, parameters)
        columnName = [c.name for c in cur.description]
        result_query = [row for row in cur.fetchall()]

        cur.close()
    except Exception as e:
        cur.close()
        raise e

    return {
        "total": str(len(result_query)),
        "results": [{"id": r[0], "text": r[1]} for r in result_query]
    }


def generate_query(key, hasTerm, is_sample, depends, kwargs):
    parameters = dict()
    conf = AutoCompleteMap.autocompletemap(key, kwargs)
    parameters['key'] = conf['key']
    parameters['value'] = conf['value']
    parameters['table'] = conf['table']
    parameters['join'] = conf['join'] if 'join' in conf else ''
    parameters['order_type'] = conf['key_type'] if 'key_type' in conf else 'string'
    
    if parameters['order_type'] == 'string':
        parameters['order_type'] = 'text'
    elif parameters['order_type'] == 'int' or parameters['order_type'] == 'integer' or parameters['order_type'] == 'float':
        parameters['order_type'] = 'float'
    else:
        parameters['order_type'] = 'text'

    # Dependências de entidades preenchidas na view
    join_depend = []
    where_depend = []
    param_depend = {}
    for d in depends:
        aux = conf['depends'][d[0]]
        join_depend.extend(aux['join'])
        where_depend.append(aux['where']%(str.join(",", ['%%(%s_%s)s'%(d[0], i) for i, x in enumerate(d[1])])))
        [param_depend.update({'%s_%s'%(d[0], i) : x}) for i, x in enumerate(d[1])]
    join_depend = list(dict.fromkeys(join_depend))
    parameters['depends_join'] = str.join("\n", join_depend)

    if hasTerm:
        whereMap = dict(table=conf['table'], value=conf['value'], exp="%(term)s")
        if conf['index'] == "gin" or conf['index'] == "gist":
            whereExp = """where ( to_tsvector('portuguese', {table}.{value}) @@ to_tsquery('portuguese',{exp}||':*') or 
            {table}.{value} ilike {exp}||'%%' or 
            {table}.{value} ilike '%%'||{exp} )""".format(**whereMap)
        else:
            whereExp = """ where ( {table}.{value} ilike '%%'||{exp}||'%%' ) """.format(**whereMap)
        parameters['where'] = "%s %s"%(whereExp, "and %s"%(str.join(" and ", where_depend)) if len(where_depend) > 0 else "")
    else:
        parameters['where'] = "where %s"%(str.join(" and ", where_depend)) if len(where_depend) > 0 else ""

    parameters['limit'] = 'limit 5' if is_sample else 'limit 100'
    sql = """
        with base as (
            select distinct {table}.{key} "key", {table}.{value} "value" 
            from {table}
            {join}
            {depends_join}
            {where}
            {limit} 
        )
        select b."key", b."value" 
        from base b
        order by b."key"::{order_type} asc
    """.format(**parameters)

    return [sql, param_depend]

class AutocompleteEndpoint(APIView):
    @extract_work
    def get(self, request, *args, **kwargs):
        pattern = re.compile('depends\[(?P<name>\w*)\]')
        key = request.GET['key']
        text = request.GET.get('q[term]') if request.GET.get('q[term]') else ''
        depends = [[pattern.findall(k)[0], request.GET[k].split('<spt_s>')] for k in request.GET.keys() if k.startswith('depends')]
        resp = get_items(key, text, depends, False, request, kwargs)

        return JsonResponse(resp)

class AutocompleteComponentEndpoint(APIView):
    @extract_work
    def get(self, request, *args, **kwargs):
        key = request.GET['key']
        mapping = AutoCompleteMap.autocompletemap(key, kwargs)
        
        context = {}
        context['icon'] = mapping['icon'] if 'icon' in mapping else ''
        context['label'] = mapping['label']
        context['depends'] = str.join(",", ["select%s" % (k,) for k in mapping['depends'].keys()] if mapping['depends'] else [])

        return JsonResponse(context)
