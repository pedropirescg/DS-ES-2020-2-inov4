import re
import json

from django.db import models
from common.general_classes import AutoCompleteMap
from django.utils.translation import ugettext_lazy as _

class CustomReportFilter:
    def __init__(self, icon, label, type, sql, items, obg, limit, count, dom_id, is_autocomplete):
        self.icon = icon
        self.label = label
        self.type = type
        self.sql = sql
        self.items = items
        self.obg = obg
        self.limit = limit
        self.count = count
        self.dom_id = dom_id
        self.is_autocomplete = is_autocomplete


class AuxDataReport:
    def __init__(self, cols, data, config):
        self.cols = cols
        self.data = data
        self.config = config

class CustomCRUD(models.Model):
    codi_crd = models.AutoField(
        primary_key=True,
        db_column="codi_crd",
        verbose_name="codi_crd",
        help_text="codi_crd",
    )

    nome_crd = models.TextField(
        null=False,
        db_column="nome_crd",
        verbose_name="nome_crd",
        help_text="nome_crd",
    )

    desc_crd = models.TextField(
        null=False,
        db_column="desc_crd",
        verbose_name="desc_crd",
        help_text="desc_crd",
    )

    flab_crd = models.TextField(
        null=False,
        db_column="flab_crd",
        verbose_name="flab_crd",
        help_text="flab_crd",
    )

    ftyp_crd = models.TextField(
        null=False,
        db_column="ftyp_crd",
        verbose_name="ftyp_crd",
        help_text="ftyp_crd",
    )

    tabl_crd = models.TextField(
        null=False,
        db_column="tabl_crd",
        verbose_name="tabl_crd",
        help_text="tabl_crd",
    )

    ftab_crd = models.TextField(
        null=False,
        db_column="ftab_crd",
        verbose_name="ftab_crd",
        help_text="ftab_crd",
    )

    conf_crd = models.TextField(
        null=False,
        db_column="conf_crd",
        verbose_name="conf_crd",
        help_text="conf_crd",
    )

    fgrp_crd = models.TextField(
        null=False,
        db_column="fgrp_crd",
        verbose_name="fgrp_crd",
        help_text="fgrp_crd",
    )

    report_db = models.CharField(
        max_length=255,
        verbose_name="Report database name",
        null=True,
        blank=True
    )

    def filters(self, entity_map):
        if self.flab_crd == None or len(self.flab_crd) == 0:
            return []

        fs = []
        radioCounter = -1
        checkboxCounter = -1
        plainFieldCounter = -1
        selectCounter = -1
        textFieldCounter = -1
        lab = self.flab_crd.split(';')
        typ = self.ftyp_crd.split(';')
        #lsql = self.customreportbody_set.first().fsql_rbd.split(';') if self.customreportbody_set.count() > 0 else []
        mapping = entity_map
        for i in range(len(lab)):
            raw_type = re.sub("\{.+?\}", "", typ[i]).split(':')[0]
            obg = typ[i].split(':')[1] == 'OBG'  if len( typ[i].split(':') ) > 1 else False
            limit = int(typ[i].split(':')[2])  if len( typ[i].split(':') ) > 2 else None
            items = re.search("\{.+?\}", typ[i]).group().replace("{", "").replace("}", "").split('|') if re.search("\{.+?\}", typ[i]) else []
            items = [i.split('<^^>') for i in items]

            dom_id = ''
            count = None
            is_autocomplete = False
            if raw_type == "SELECT":
                selectCounter = selectCounter + 1
                count = selectCounter
                dom_id = "selectTag%s"%(count)
            elif raw_type == "RADIO":
                radioCounter = radioCounter + 1
                count = radioCounter
                dom_id = "divselectRADIO%s"%(count)
            elif raw_type == "CHECKBOX":
                checkboxCounter = checkboxCounter + 1
                count = checkboxCounter
                dom_id = "divselectCHECKBOX%s"%(count)
            elif raw_type == "TEXT":
                textFieldCounter = textFieldCounter + 1
                count = textFieldCounter
                dom_id = "textField%s"%(count)
            elif raw_type in ["NINT32", "NINT64", "IINT32", "IINT64", "FLOAT"]:
                plainFieldCounter = plainFieldCounter + 1
                count = plainFieldCounter
                dom_id = "plainField%s%s"%(raw_type, count)
            elif raw_type in ["DATEBTW", "DATA"]:
                dom_id = "date-interval"
            else:
                dom_id = "select%s"%(raw_type)
                is_autocomplete = True
            

            default_label = ''
            default_icon = ''
            if raw_type in mapping:
                default_label = str(mapping[raw_type]['label'])
                default_icon = str(mapping[raw_type]['icon'] if 'icon' in mapping[raw_type] else '')

            
            if lab[i] == '':
                curr_label = default_label
                curr_icon = default_icon
            elif 'icon:' in lab[i] or 'label:' in lab[i]:
                sel_label = [l[6:] for l in lab[i].split('|') if l.startswith('label:') ]
                sel_icon = [l[5:] for l in lab[i].split('|') if l.startswith('icon:') ]
                curr_label = ( sel_label[0] if len(sel_label) > 0 else default_label )
                curr_icon = ( sel_icon[0] if len(sel_icon) > 0 else default_icon )
            else:
                curr_label = lab[i]
                curr_icon = ''


            fs.append(CustomReportFilter(label=curr_label, icon=curr_icon, type = raw_type, sql = None, items=items, obg=obg, limit=limit, count=count, dom_id=dom_id, is_autocomplete = is_autocomplete))
        
        return fs
    class Meta:
        db_table = "customcrud"

class CustomReport(models.Model):
    codi_rep = models.AutoField(
        primary_key=True,
        db_column="codi_rep",
        verbose_name="codi_rep",
        help_text="codi_rep",
    )

    nome_rep = models.TextField(
        null=False,
        db_column="nome_rep",
        verbose_name="nome_rep",
        help_text="nome_rep",
    )

    desc_rep = models.TextField(
        null=False,
        db_column="desc_rep",
        verbose_name="desc_rep",
        help_text="desc_rep",
    )

    flab_rep = models.TextField(
        null=False,
        db_column="flab_rep",
        verbose_name="flab_rep",
        help_text="flab_rep",
    )

    ftyp_rep = models.TextField(
        null=False,
        db_column="ftyp_rep",
        verbose_name="ftyp_rep",
        help_text="ftyp_rep",
    )

    fgrp_rep = models.TextField(
        null=False,
        db_column="fgrp_rep",
        verbose_name="fgrp_rep",
        help_text="fgrp_rep",
    )

    codi_usu = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="codi_usu",
        db_column='codi_usu',
        help_text="codi_usu"
    )

    company = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="company",
        db_column='company',
        help_text="company"
    )

    report_db = models.CharField(
        max_length=255,
        verbose_name="Report database name",
        null=True,
        blank=True
    )

    def filters(self, entity_map):
        if self.flab_rep == None or len(self.flab_rep) == 0:
            return []

        fs = []
        radioCounter = -1
        checkboxCounter = -1
        plainFieldCounter = -1
        selectCounter = -1
        textFieldCounter = -1
        lab = self.flab_rep.split(';')
        typ = self.ftyp_rep.split(';')
        lsql = self.customreportbody_set.first().fsql_rbd.split(';') if self.customreportbody_set.count() > 0 else []
        mapping = entity_map
        for i in range(len(lab)):
            raw_type = re.sub("\{.+?\}", "", typ[i]).split(':')[0]
            obg = typ[i].split(':')[1] == 'OBG'  if len( typ[i].split(':') ) > 1 else False
            limit = int(typ[i].split(':')[2])  if len( typ[i].split(':') ) > 2 else None
            items = re.search("\{.+?\}", typ[i]).group().replace("{", "").replace("}", "").split('|') if re.search("\{.+?\}", typ[i]) else []
            items = [i.split('<^^>') for i in items]

            dom_id = ''
            count = None
            is_autocomplete = False
            if raw_type == "SELECT":
                selectCounter = selectCounter + 1
                count = selectCounter
                dom_id = "selectTag%s"%(count)
            elif raw_type == "RADIO":
                radioCounter = radioCounter + 1
                count = radioCounter
                dom_id = "divselectRADIO%s"%(count)
            elif raw_type == "CHECKBOX":
                checkboxCounter = checkboxCounter + 1
                count = checkboxCounter
                dom_id = "divselectCHECKBOX%s"%(count)
            elif raw_type == "TEXT":
                textFieldCounter = textFieldCounter + 1
                count = textFieldCounter
                dom_id = "textField%s"%(count)
            elif raw_type in ["NINT32", "NINT64", "IINT32", "IINT64", "FLOAT"]:
                plainFieldCounter = plainFieldCounter + 1
                count = plainFieldCounter
                dom_id = "plainField%s%s"%(raw_type, count)
            elif raw_type in ["DATEBTW", "DATA"]:
                dom_id = "date-interval"
            else:
                dom_id = "select%s"%(raw_type)
                is_autocomplete = True
            

            default_label = ''
            default_icon = ''
            if raw_type in mapping:
                default_label = str(mapping[raw_type]['label'])
                default_icon = str(mapping[raw_type]['icon'] if 'icon' in mapping[raw_type] else '')

            
            if lab[i] == '':
                curr_label = default_label
                curr_icon = default_icon
            elif 'icon:' in lab[i] or 'label:' in lab[i]:
                sel_label = [l[6:] for l in lab[i].split('|') if l.startswith('label:') ]
                sel_icon = [l[5:] for l in lab[i].split('|') if l.startswith('icon:') ]
                curr_label = ( sel_label[0] if len(sel_label) > 0 else default_label )
                curr_icon = ( sel_icon[0] if len(sel_icon) > 0 else default_icon )
            else:
                curr_label = lab[i]
                curr_icon = ''


            fs.append(
                CustomReportFilter(
                    label=curr_label, 
                    icon=curr_icon, 
                    type = raw_type, 
                    sql = lsql[i] if len(lsql) > i else '', 
                    items=items, 
                    obg=obg, 
                    limit=limit, 
                    count=count, 
                    dom_id=dom_id, 
                    is_autocomplete=is_autocomplete
                    )
            )
        
        return fs
        
    class Meta:
        db_table = "customreportheader"


class CustomReportBody(models.Model):
    codi_rbd = models.AutoField(
        primary_key=True,
        db_column="codi_rbd",
        verbose_name="codi_rbd",
        help_text="codi_rbd",
    )

    nome_rbd = models.TextField(
        null=False,
        db_column="nome_rbd",
        verbose_name="nome_rbd",
        help_text="nome_rbd",
    )

    desc_rbd = models.TextField(
        null=False,
        db_column="desc_rbd",
        verbose_name="desc_rbd",
        help_text="desc_rbd",
    )

    ssql_rbd = models.TextField(
        null=False,
        db_column="ssql_rbd",
        verbose_name="ssql_rbd",
        help_text="ssql_rbd",
    )

    fsql_rbd = models.TextField(
        null=False,
        db_column="fsql_rbd",
        verbose_name="fsql_rbd",
        help_text="fsql_rbd",
    )

    type_rbd = models.TextField(
        null=False,
        db_column="type_rbd",
        verbose_name="type_rbd",
        help_text="type_rbd",
    )

    ordr_rbd = models.TextField(
        null=False,
        db_column="ordr_rbd",
        verbose_name="ordr_rbd",
        help_text="ordr_rbd",
    )

    conf_rbd = models.TextField(
        null=False,
        db_column="conf_rbd",
        verbose_name="conf_rbd",
        help_text="conf_rbd",
    )

    codi_rep = models.ForeignKey(
        CustomReport,
        on_delete=models.PROTECT,
        db_column="codi_rep",
        verbose_name="codi_rep",
        help_text="codi_rep foreignkey",
    )

    class Meta:
        db_table = "customreportbody"


class CustomReportBodyExtra(models.Model):
    codi_rbx = models.AutoField(
        primary_key=True,
        db_column="codi_rbx",
        verbose_name="codi_rbx",
        help_text="codi_rbx",
    )

    desc_rbx = models.TextField(
        null=False,
        db_column="desc_rbx",
        verbose_name="desc_rbx",
        help_text="desc_rbx",
    )

    ssql_rbx = models.TextField(
        null=False,
        db_column="ssql_rbx",
        verbose_name="ssql_rbx",
        help_text="ssql_rbx",
    )

    type_rbx = models.TextField(
        null=False,
        db_column="type_rbx",
        verbose_name="type_rbx",
        help_text="type_rbx",
    )

    comp_rbx = models.TextField(
        null=False,
        db_column="comp_rbx",
        verbose_name="comp_rbx",
        help_text="comp_rbx",
    )

    freq_rbx = models.TextField(
        null=False,
        db_column="freq_rbx",
        verbose_name="freq_rbx",
        help_text="freq_rbx",
    )

    cdom_rbx = models.TextField(
        null=False,
        db_column="cdom_rbx",
        verbose_name="cdom_rbx",
        help_text="cdom_rbx",
    )

    codi_rbd = models.ForeignKey(
        CustomReportBody,
        on_delete=models.PROTECT,
        db_column="codi_rbd",
        verbose_name="codi_rbd",
        help_text="codi_rbd foreignkey",
    )

    class Meta:
        db_table = "customreportbodyextra"

class CustomReportConfig(models.Model):
    codi_rep = models.OneToOneField(
        CustomReport,
        primary_key=True,
        on_delete=models.PROTECT,
        db_column="codi_rep",
        verbose_name="codi_rep",
        help_text="codi_rep foreignkey",
    )

    para_rcf = models.TextField(
        null=False,
        db_column="para_rcf",
        verbose_name="para_rcf",
        help_text="para_rcf",
    )

    freq_rcf = models.IntegerField(
        null=False,
        db_column="freq_rcf",
        verbose_name="freq_rcf",
        help_text="freq_rcf",
    )

    path_rcf = models.TextField(
        null=True,
        db_column="path_rcf",
        verbose_name="path_rcf",
        help_text="path_rcf",
    )

    stru_rcf = models.TextField(
        null=False,
        db_column="stru_rcf",
        verbose_name="stru_rcf",
        help_text="stru_rcf",
    )

    class Meta:
        db_table = "customreportconfig"