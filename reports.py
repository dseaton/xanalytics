#
# report methods
#

import os
import csv
import codecs
import models
import datetime
import logging
import webapp2
import json
import re
import hashlib

import jinja2

import gsdata
import bqutil
import auth

import local_config

from models import CustomReport
from jinja2 import Template
from collections import defaultdict, OrderedDict
from stats import DataStats
from datatable import DataTableField
from datasource import DataSource

from auth import auth_required, auth_and_role_required
from templates import JINJA_ENVIRONMENT

from google.appengine.api import memcache
mem = memcache.Client()

class Reports(object):
    '''
    This class is meant to be mixed-in
    '''

    def custom_report_container(self, is_authorized_for_custom_report, **pdata):
        '''
        Return object which acts like a dict and can be used to generate HTML fragment as container for specified custom report.

        pdata = parameter data for custom report (also goes into authorization check)
        '''
        other = self
        class CRContainer(dict):
            def __init__(self, *args, **kwargs):
                self.immediate_view = False
                super(CRContainer, self).__init__(*args, **kwargs)

            @property
            def immediate(self):
                self.immediate_view = True
                return self

            @property
            def parameter(self):
                crc = self
                class ParameterSetter(dict):
                    def __getitem__(self, parameter_name):
                        class ParameterValue(dict):
                            def __getitem__(self, parameter_value):
                                logging.info("CRContainer setting parameter %s = %s" % (parameter_name, parameter_value))
                                pdata[parameter_name] = parameter_value
                                return crc
                        return ParameterValue()
                return ParameterSetter()

            def __getitem__(self, report_name):
                try:
                    crm = other.get_custom_report_metadata(report_name)
                    err = None
                except Exception as err:
                    crm = None
                if not crm:
                    logging.info("No custom report '%s' found, err=%s" % (report_name, err))
                    return "Missing custom report %s" % report_name

                # check access authorization
                # logging.info('[crc] checking auth for report %s, pdata=%s' % (crm.name, pdata))
                auth_ok, msg = is_authorized_for_custom_report(crm, pdata)
                if not auth_ok:
                    return ""			# return empty string if not authorized
                
                title = JINJA_ENVIRONMENT.from_string(crm.title)
                title_rendered = title.render(pdata)
                parameters = {x:v for x,v in pdata.items() if v is not None}

                report_id = hashlib.sha224("%s %s" % (crm.name, json.dumps(pdata))).hexdigest()

                template = JINJA_ENVIRONMENT.get_template('custom_report_container.html')
                data = {'is_staff': other.is_superuser(),
                        'report': crm,
                        'report_params': json.dumps(parameters),
                        'report_is_staff': pdata.get('staff'),
                        'report_meta_info': json.dumps(crm.meta_info),
                        'immediate_view': json.dumps(self.immediate_view),
                        'title': title_rendered,
                        'id': report_id,
                }
                self.immediate_view = False	# return to non-immediate view by default
                return template.render(data)
        return CRContainer()
    
