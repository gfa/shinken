#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
#    Andreas Karfusehr, andreas@karfusehr.de
#
# This file is part of Shinken.
#
# Shinken is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Shinken is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Shinken.  If not, see <http://www.gnu.org/licenses/>.

import time
import copy
import math
from pprint import pprint
try:
    import json
except ImportError:
    # For old Python version, load
    # simple json (it can be hard json?! It's 2 functions guy!)
    try:
        import simplejson as json
    except ImportError:
        print "Error: you need the json or simplejson module"
        raise

from shinken.util import safe_print
from shinken.misc.perfdata import PerfDatas
from shinken.misc.sorter import hst_srv_sort
# TODO: manage it in a clean way.
from shinken.modules.webui_broker.perfdata_guess import get_perfometer_table_values


class Helper(object):
    def __init__(self):
        pass

    def gogo(self):
        return 'HELLO'

    def act_inactive(self, b):
        if b:
            return 'Active'
        else:
            return 'Inactive'

    def yes_no(self, b):
        if b:
            return 'Yes'
        else:
            return 'No'

    def print_float(self, f):
        return '%.2f' % f

    def ena_disa(self, b):
        if b:
            return 'Enabled'
        else:
            return 'Disabled'

    # For a unix time return something like
    # Tue Aug 16 13:56:08 2011
    def print_date(self, t):
        if t == 0 or t == None:
            return 'N/A'
        return time.asctime(time.localtime(t))

    # For a time, print something like
    # 10m 37s  (just duration = True)
    # N/A if got bogus number (like 1970 or None)
    # 1h 30m 22s ago (if t < now)
    # Now (if t == now)
    # in 1h 30m 22s
    # Or in 1h 30m (no sec, if we ask only_x_elements=2, 0 means all)
    def print_duration(self, t, just_duration=False, x_elts=0):
        if t == 0 or t == None:
            return 'N/A'
        #print "T", t
        # Get the difference between now and the time of the user
        seconds = int(time.time()) - int(t)

        # If it's now, say it :)
        if seconds == 0:
            return 'Now'

        in_future = False

        # Remember if it's in the future or not
        if seconds < 0:
            in_future = True

        # Now manage all case like in the past
        seconds = abs(seconds)
        #print "In future?", in_future

        #print "sec", seconds
        seconds = long(round(seconds))
        #print "Sec2", seconds
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        weeks, days = divmod(days, 7)
        months, weeks = divmod(weeks, 4)
        years, months = divmod(months, 12)

        minutes = long(minutes)
        hours = long(hours)
        days = long(days)
        weeks = long(weeks)
        months = long(months)
        years = long(years)

        duration = []
        if years > 0:
            duration.append('%dy' % years)
        else:
            if months > 0:
                duration.append('%dM' % months)
            if weeks > 0:
                duration.append('%dw' % weeks)
            if days > 0:
                duration.append('%dd' % days)
            if hours > 0:
                duration.append('%dh' % hours)
            if minutes > 0:
                duration.append('%dm' % minutes)
            if seconds > 0:
                duration.append('%ds' % seconds)

        #print "Duration", duration
        # Now filter the number of printed elements if ask
        if x_elts >= 1:
            duration = duration[:x_elts]

        # Maybe the user just want the duration
        if just_duration:
            return ' '.join(duration)

        # Now manage the future or not print
        if in_future:
            return 'in ' + ' '.join(duration)
        else:  # past :)
            return ' '.join(duration) + ' ago'


    # Need to create a X level higher and lower to the element
    def create_json_dep_graph(self, elt, levels=3):
        t0 = time.time()
        # First we need ALL elements
        all_elts = self.get_all_linked_elts(elt, levels=levels)

        #print "We got all our elements"
        dicts = []
        for i in all_elts:
            #safe_print("Elt", i.get_dbg_name())
            ds = self.get_dep_graph_struct(i)
            for d in ds:
                dicts.append(d)
        j = json.dumps(dicts)
        #safe_print("Create json", j)
        #pprint(dicts)
        #print "create_json_dep_graph::Json creation time", time.time() - t0
        return j

    # Return something like:
    # {
    #                  "id": "localhost",
    #                  "name": "localhost",
    #                  "data": {"$color":"red", "$dim": 5*2, "some other key": "some other value"},
    #                  "adjacencies": [{
    #                          "nodeTo": "main router",
    #                          "data": {
    #                              "$type":"arrow",
    #                              "$color":"gray",
    #                              "weight": 3,
    #                              "$direction": ["localhost", "main router"],
    #                          }
    #                      }
    #                      ]
    #              }
    # But as a python dict

    def get_all_nodes_from_aggregation_node(self, tree):
        res = [{'path' : tree['path'], 'services': tree['services'], 'state': tree['state'], 'full_path': tree['full_path']}]
        for s in tree['sons']:
            r = self.get_all_nodes_from_aggregation_node(s)
            for n in r:
                res.append(n)
        return res
            
        

    def create_dep_graph_aggregation_node(self, elt):
        # {'path' : '/', 'sons' : [], 'services':[], 'state':'unknown', 'full_path':'/'}
        hname = elt.get_name()
        tree = self.get_host_service_aggregation_tree(elt)
        all_nodes = self.get_all_nodes_from_aggregation_node(tree)
        #print "aLL NODES"
        #pprint(all_nodes)

        res = []
        for n in all_nodes:
            d = {'id': self.strip_html_id(hname+n['full_path']), 'name': n['full_path'],
                 'data': {'$type': 'custom',
                          'business_impact': 2,#elt.business_impact,
                          'img_src': '/static/img/icons/state_%s.png' % n['state'],
                          },
                 'adjacencies': []
                 }
            # Set the right info panel
            d['data']['infos'] = ''#r''' %s ''' % self.strip_html_id(n['full_path'])
            d['data']['elt_type'] = 'service'
            d['data']['is_problem'] = False
            d['data']['state_id'] = 1
            d['data']['circle'] = 'none'

            # by default the father linkis the host
            father =  elt.get_dbg_name()
            # But if the aggregation is a level1+ it must be the level-1 one
            #print "FULL PATH"*20, n['full_path'], n['full_path'].count('/'), self.get_aggregation_paths(n['full_path'])
            agg_parts = [s for s in self.get_aggregation_paths(n['full_path']) if s]

            # Root, no block for it
            if len(agg_parts) == 0:
                continue
            # For 1, it'smeans first agg level, so our father is the host
            # but it's already set. For >1, the father is the agg level before
            if len(agg_parts) > 1:
                pre_path = '/'+'/'.join(agg_parts[:-1])
                father = self.strip_html_id(elt.get_dbg_name()+pre_path)
                

            pd = {'nodeTo': father,
                  'data': {"$type": "line", "$direction": [self.strip_html_id(d['id']), elt.get_dbg_name()]
                           }
                  }
            if n['state'].lower() in ['warning', 'critical']:
                pd['data']["$color"] = 'Tomato'
            else:
                pd['data']["$color"] = 'PaleGreen'
            d['adjacencies'].append(pd)
            
            res.append(d)

        return res
    

    def get_dep_graph_struct(self, elt):
        t = elt.__class__.my_type

        # We set the values for webui/plugins/depgraph/htdocs/js/eltdeps.js
        # so a node with important data for rendering
        # type = custom, business_impact and img_src.
        d = {'id': elt.get_dbg_name(), 'name': elt.get_dbg_name(),
             'data': {'$type': 'custom',
                       'business_impact': elt.business_impact,
                       'img_src': self.get_icon_state(elt),
                       },
             'adjacencies': []
             }
        res = [d]

        # if we got an host, compute the aggregation part
        if t == 'host':
            nodes = self.create_dep_graph_aggregation_node(elt)
            for n in nodes:
                res.append(n)

        
        # Set the right info panel
        d['data']['infos'] = r'''%s <h2 class="%s"><img style="width: 64px; height:64px" src="%s"/> %s: %s</h2>
                   <p>since %s</p>
                   <div style="float:right;"> <a href="%s">%s</a></div>''' % (
            '<img src="/static/img/icons/star.png" alt="star">' * (elt.business_impact - 2),
            elt.state.lower(), self.get_icon_state(elt), elt.state, elt.get_full_name(),
            self.print_duration(elt.last_state_change, just_duration=True, x_elts=2),
            self.get_link_dest(elt), self.get_button('Go to details', img='/static/images/search.png'))

        d['data']['elt_type'] = elt.__class__.my_type
        d['data']['is_problem'] = elt.is_problem
        d['data']['state_id'] = elt.state_id

        #safe_print("ELT:%s is %s" % (elt.get_full_name(), elt.state))
        if elt.state in ['OK', 'UP', 'PENDING']:
            d['data']['circle'] = 'none'
        elif elt.state in ['DOWN', 'CRITICAL']:
            d['data']['circle'] = 'red'
        elif elt.state in ['WARNING', 'UNREACHABLE']:
            d['data']['circle'] = 'orange'
        else:
            d['data']['circle'] = 'none'
        
        
        # Now put in adj our parents
        for p in elt.parent_dependencies:
            # The link service-> host can be squize by aggregations if set
            if t == 'service' and elt.aggregation and p == elt.host:
                agg_name = '/'.join(self.get_aggregation_paths(elt.aggregation))
                agg_id = self.strip_html_id(p.get_dbg_name()+agg_name)
                pd = {'nodeTo': agg_id,
                      'data': {"$type": "line", "$direction": [elt.get_dbg_name(), agg_id]
                               }
                      }
            else: # Ok a basic link with the element and elt so
                pd = {'nodeTo': p.get_dbg_name(),
                      'data': {"$type": "line", "$direction": [elt.get_dbg_name(), p.get_dbg_name()]
                               }
                      }

            # Naive way of looking at impact
            if elt.state_id != 0 and p.state_id != 0:
                pd['data']["$color"] = 'Tomato'
            # If OK, show host->service as a green link
            elif elt.__class__.my_type != p.__class__.my_type:
                pd['data']["$color"] = 'PaleGreen'
            d['adjacencies'].append(pd)

        # The sons case is now useful, it will be done by our sons
        # that will link us
        return res


    # Return all linked elements of this elt, and 2 level
    # higher and lower :)
    def get_all_linked_elts(self, elt, levels=3):
        if levels == 0:
            return set()

        my = set()
        for i in elt.child_dependencies:
            my.add(i)
            child_elts = self.get_all_linked_elts(i, levels=levels - 1)
            for c in child_elts:
                my.add(c)
        for i in elt.parent_dependencies:
            my.add(i)
            par_elts = self.get_all_linked_elts(i, levels=levels - 1)
            for c in par_elts:
                my.add(c)

        #safe_print("get_all_linked_elts::Give elements", my)
        return my


    # Return a button with text, image, id and class (if need)
    def get_button(self, text, img=None, id=None, cls=None):
        #s = '<div class="buttons">\n'
        s = '<div class="btn">\n'
        if cls and not id:
            s += '<div class="%s">\n' % cls
        elif id and not cls:
            s += '<div id="%s">\n' % id
        elif id and cls:
            s += '<div class="%s" id="%s">\n' % (cls, id)
        else:
            s += '<div>\n'
        if img:
            s += '<img src="%s" alt=""/>\n' % img
        s += "%s" % text
        s += ''' </div>
            </div>\n'''

        return s

    # For and host, return the services sorted by business
    # impact, then state, then desc
    def get_host_services_sorted(self, host):
        t = copy.copy(host.services)
        t.sort(hst_srv_sort)
        return t

    def get_input_bool(self, b, id=None):
        id_s = ''
        if id:
            id_s = 'id="%s"' % id
        if b:
            return """<input type="checkbox" checked="checked" %s/>\n""" % id_s
        else:
            return """<input type="checkbox" %s />\n""" % id_s


    def print_business_rules_mobile(self, tree, level=0, source_problems=[]):
        #safe_print("Should print tree", tree)
        #safe_print('with source_problems', source_problems)
        node = tree['node']
        name = node.get_full_name()
        fathers = tree['fathers']
        fathers = sorted(fathers, key=lambda dict: dict['node'].get_full_name())
        s = ''
        # Maybe we are the root problem of this, and so we are printing it
        root_str = ''
        if node in source_problems:
            #print "I am a root problem"
            root_str = ' <span class="alert-small alert-critical"> Root problem</span>'
        # Do not print the node if it's the root one, we already know its state!
        if level != 0:
            s += "%s is %s since %s %s\n" % (self.get_link_mobile(node), node.state, self.print_duration(node.last_state_change, just_duration=True), root_str)

        # If we got no parents, no need to print the expand icon
        if len(fathers) > 0:
            # We look if the below tree is goodor not
            tree_is_good = (node.state_id == 0)

            # If the tree is good, we will use an expand image
            # and hide the tree
            if tree_is_good:
                display = 'none'
                img = 'expand.png'
            else:  # we will already show the tree, and use a reduce image
                display = 'block'
                img = 'reduce.png'

            s += """<ul id="business-parents-%s" style="display: %s; ">""" % (name, display)

            for n in fathers:
                sub_node = n['node']
                sub_s = self.print_business_rules_mobile(n, level=level+1, source_problems=source_problems)
                s += '<li class="%s">%s</li>' % (self.get_small_icon_state(sub_node), sub_s)
            s += "</ul>"
        #safe_print("Returning s:", s)
        return s


    def print_business_rules(self, tree, level=0, source_problems=[]):
        #safe_print("Should print tree", tree)
        #safe_print('with source_problems', source_problems)
        node = tree['node']
        name = node.get_full_name()
        fathers = tree['fathers']
        fathers = sorted(fathers, key=lambda dict: dict['node'].get_full_name())
        s = ''

        # Maybe we are the root problem of this, and so we are printing it
        root_str = ''
        if node in source_problems:
            #print "I am a root problem"
            root_str = ' <span class="alert-small alert-critical"> Root problem</span>'
        # Do not print the node if it's the root one, we already know its state!
        if level != 0:
            s += "%s is %s since %s %s\n" % (self.get_link(node), node.state, self.print_duration(node.last_state_change, just_duration=True), root_str)

        # If we got no parents, no need to print the expand icon
        if len(fathers) > 0:
            # We look if the below tree is goodor not
            tree_is_good = (node.state_id == 0)

            # If the tree is good, we will use an expand image
            # and hide the tree
            if tree_is_good:
                display = 'none'
                img = 'expand.png'
            else:  # we will already show the tree, and use a reduce image
                display = 'block'
                img = 'reduce.png'

            # If we are the root, we already got this
            if level != 0:
                s += """<a id="togglelink-%s" href="javascript:toggleBusinessElt('%s')"><img id="business-parents-img-%s" src="/static/images/%s" alt="toggle"> </a> \n""" % (name, name, name, img)

            s += """<ul id="business-parents-%s" style="display: %s; ">""" % (name, display)

            for n in fathers:
                sub_node = n['node']
                sub_s = self.print_business_rules(n, level=level+1, source_problems=source_problems)
                s += '<li class="%s">%s</li>' % (self.get_small_icon_state(sub_node), sub_s)
            s += "</ul>"
        #safe_print("Returning s:", s)
        return s

    # Mockup helper
    # User: Frescha
    # Date: 08.01.2012
    def print_business_tree(self, tree, level=0):
        #safe_print("Should print tree", tree)
        node = tree['node']
        name = node.get_full_name()
        fathers = tree['fathers']
        fathers = sorted(fathers, key=lambda dict: dict['node'].get_full_name())
        s = ''
        # Do not print the node if it's the root one, we already know its state!
        if level != 0:
            s += "%s is %s since %s\n" % (self.get_link(node), node.state, self.print_duration(node.last_state_change, just_duration=True))

        # If we got no parents, no need to print the expand icon
        if len(fathers) > 0:
            # We look if the below tree is goodor not
            tree_is_good = (node.state_id == 0)

            # If the tree is good, we will use an expand image
            # and hide the tree
            if tree_is_good:
                display = 'none'
                img = 'expand.png'
            else:  # we will already show the tree, and use a reduce image
                display = 'block'
                img = 'reduce.png'

            # If we are the root, we already got this
            if level != 0:
                s += """<a id="togglelink-%s" href="javascript:toggleBusinessElt('%s')"><img id="business-parents-img-%s" src="/static/images/%s" alt="toggle"> </a> \n""" % (name, name, name, img)

            s += """<ul id="business-parents-%s" class="treeview" style="display: %s; ">""" % (name, display)

            for n in fathers:
                sub_node = n['node']
                sub_s = self.print_business_rules(n, level=level+1)
                s += '<li class="%s">%s</li>' % (self.get_small_icon_state(sub_node), sub_s)
            s += "</ul>"
        #safe_print("Returning s:", s)
        return s

    # Get the small state for host/service icons
    # and satellites ones
    def get_small_icon_state(self, obj):
        if obj.__class__.my_type in ['service', 'host']:
            if obj.state == 'PENDING':
                return 'unknown'
            if obj.state == 'OK':
                return 'ok'
            if obj.state == 'UP':
                return 'up'
            # Outch, not a good state...
            if obj.problem_has_been_acknowledged:
                return 'ack'
            if obj.in_scheduled_downtime:
                return 'downtime'
            if obj.is_flapping:
                return 'flapping'
            # Ok, no excuse, it's a true error...
            return obj.state.lower()
        # Maybe it's a satellite
        if obj.__class__.my_type in ['scheduler', 'poller',
                                     'reactionner', 'broker',
                                     'receiver']:
            if not obj.alive:
                return 'critical'
            if not obj.reachable:
                return 'warning'
            return 'ok'
        return 'unknown'

    # For an object, give it's business impact as text
    # and stars if need
    def get_business_impact_text(self, obj):
        txts = {0: 'None', 1: 'Low', 2: 'Normal',
                3: 'High', 4: 'Very important', 5: 'Top for business'}
        nb_stars = max(0, obj.business_impact - 2)
        stars = '<img src="/static/img/icons/star.png" alt="star">\n' * nb_stars

        res = "%s %s" % (txts.get(obj.business_impact, 'Unknown'), stars)
        return res

    # We will output as a ul/li list the impacts of this
    def got_impacts_list_as_li(self, obj):
        impacts = obj.impacts
        r = '<ul>\n'
        for i in impacts:
            r += '<li>%s</li>\n' % i.get_full_name()
        r += '</ul>\n'
        return r

    # Return the impacts as a business sorted list
    def get_impacts_sorted(self, obj):
        t = copy.copy(obj.impacts)
        t.sort(hst_srv_sort)
        return t

    def get_link(self, obj, short=False, mobile=False):
        if obj.__class__.my_type == 'service':
            if short:
                name = obj.get_name()
            else:
                name = obj.get_full_name()

            if mobile == False:
                return '<a href="/service/%s"> %s </a>' % (obj.get_full_name(), name)
            else:
                return '<a href="/mobile/service/%s"> %s </a>' % (obj.get_full_name(), name)
        # if not service, host
        if mobile == False:
            return '<a href="/host/%s"> %s </a>' % (obj.get_full_name(), obj.get_full_name())
        else:
            return '<a href="/mobile/host/%s"> %s </a>' % (obj.get_full_name(), obj.get_full_name())

    def get_link_mobile(self, obj, short=False):
        if obj.__class__.my_type == 'service':
            if short:
                name = obj.get_name()
            else:
                name = obj.get_full_name()
            return '<a href="/mobile/service/%s" rel="external"> %s </a>' % (obj.get_full_name(), name)
        # if not service, host
        return '<a href="/mobile/host/%s" rel="external"> %s </a>' % (obj.get_full_name(), obj.get_full_name())

    # Give only the /service/blabla or /host blabla string, like for buttons inclusion
    def get_link_dest(self, obj):
        return "/%s/%s" % (obj.__class__.my_type, obj.get_full_name())

    # For an host, give it's own link, for a services, give the link of its host
    def get_host_link(self, obj):
        if obj.__class__.my_type == 'service':
            return self.get_link(obj.host)
        return self.get_link(obj)

    # For an object, return the path of the icons
    def get_icon_state(self, obj):
        ico = self.get_small_icon_state(obj)
        if getattr(obj, 'icon_set', '') != '':
            return '/static/images/sets/%s/state_%s.png' % (obj.icon_set, ico)
        else:
            return '/static/img/icons/state_%s.png' % ico

    # Get
    def get_navi(self, total, pos, step=30):
        step = float(step)
        nb_pages = math.ceil(total / step)
        current_page = int(pos / step)

        step = int(step)

        res = []

        if nb_pages == 0 or nb_pages == 1:
            return None

        if current_page >= 2:
            # Name, start, end, is_current
            res.append((u'« First', 0, step, False))
            res.append(('...', None, None, False))

        #print "Range,", current_page - 1, current_page + 1
        for i in xrange(current_page - 1, current_page + 2):
            if i < 0:
                continue
            #print "Doing PAGE", i
            is_current = (i == current_page)
            start = int(i * step)
            # Maybe we are generating a page too high, bail out
            if start > total:
                continue

            end = int((i+1) * step)
            res.append(('%d' % (i+1), start, end, is_current))

        if current_page < nb_pages - 2:
            start = int((nb_pages - 1) * step)
            end = int(nb_pages * step)
            res.append(('...', None, None, False))
            res.append((u'Last »', start, end, False))

        #print "Total:", total, "pos", pos, "step", step
        #print "nb pages", nb_pages, "current_page", current_page

        #print "Res", res

        return res

    # Get a perfometer part for html printing
    def get_perfometer(self, elt):
        if elt.perf_data != '':
            r = get_perfometer_table_values(elt)
            # If the perfmeter are not good, bail out
            if r is None:
                return '\n'

            lnk = r['lnk']
            metrics = r['metrics']
            title = r['title']
            s = '<a href="%s">' % lnk
            s += '''<div class="graph">
                       <table>
                          <tbody>
                            <tr>\n'''

            for (color, pct) in metrics:
                s += '            <td style="background-color: %s; width: %s%%;"></td>\n' % (color, pct)

            s += '''        </tr>
                         </tbody>
                      </table>
                    </div>
                    <div class="text">%s</div>
                    <img class="glow" src="/static/images/glow.png"/>
                 </a>\n''' % title
            return s
        return '\n'

    # TODO: Will look at the string s, and return a clean output without
    # danger for the browser
    def strip_html_output(self, s):
        return s

    # We want the html id of an hostor a service. It's basically
    # the full_name with / changed as -- (because in html, / is not valid :) )
    def get_html_id(self, elt):
        return self.strip_html_id(elt.get_full_name())

    def strip_html_id(self, s):
        return s.replace('/', '--').replace(' ', '_').replace('.', '_').replace(':', '_')

    # URI with spaces are BAD, must change them with %20
    def get_uri_name(self, elt):
        return elt.get_full_name().replace(' ', '%20')

    # say if this user can launch an action or not
    def can_action(self, user):
        return user.is_admin or user.can_submit_commands


    def get_aggregation_paths(self, p):
        p = p.strip()
        if p and not p.startswith('/'):
            p = '/'+p
        if p.endswith('/'):
            p = p[-1]
        return [s.strip() for s in p.split('/')]


    def compute_aggregation_tree_worse_state(self, tree):
        # First ask to our sons to compute their states
        for s in tree['sons']:
            self.compute_aggregation_tree_worse_state(s)
        # Ok now we can look at worse between our services
        # and our sons
        # get a list of all states
        states = [s['state'] for s in tree['sons']]
        for s in tree['services']:
            states.append(s.state.lower())
        # ok now look at what is worse here
        order = ['critical', 'warning', 'unknown', 'ok', 'pending']
        for o in order:
            if o in states:
                tree['state'] = o
                return
        # Should be never call or we got a major problem...
        tree['state'] = 'unknown'
        

    def assume_and_get_path_in_tree(self, tree, paths):
        #print "Tree on start of", paths, tree
        current_full_path = ''
        for p in paths:
            # Don't care about void path, like for root
            if not p:
                continue
            current_full_path += '/'+p
            founded = False
            for s in tree['sons']:
                # Maybe we find the good son, if so go on this level
                if p == s['path']:
                    tree = s
                    founded = True
                    break
            # Did we find our son? If no, create it and jump into it
            if not founded:
                s = {'path' : p, 'sons' : [], 'services':[], 'state':'unknown', 'full_path':current_full_path}
                tree['sons'].append(s)
                tree = s
        return tree
                

    


    def get_host_service_aggregation_tree(self, h):
        tree = {'path' : '/', 'sons' : [], 'services':[], 'state':'unknown', 'full_path':'/'}
        for s in h.services:
            p = s.aggregation
            paths = self.get_aggregation_paths(p)
            #print "Service", s.get_name(), "with path", paths
            leaf = self.assume_and_get_path_in_tree(tree, paths)
            leaf['services'].append(s)
        self.compute_aggregation_tree_worse_state(tree)
        
        return tree


    def print_aggregation_tree(self, tree, html_id):
        path = tree['path']
        full_path = tree['full_path']
        sons = tree['sons']
        services = tree['services']
        state = tree['state']
        _id = '%s-%s' % (html_id, self.strip_html_id(full_path))
        s = ''

        display = 'block'
        img = 'reduce.png'

        if path != '/':
            # If our state is OK, hide our sons
            if state == 'ok':
                display = 'none'
                img = 'expand.png'

            s += """<span class="alert-small alert-%s"> %s </span>""" % (state, path)
            s += """<a id="togglelink-aggregation-%s" href="javascript:toggleAggregationElt('%s')"><img id="aggregation-toggle-img-%s" src="/static/images/%s" alt="toggle"> </a> \n""" % (_id, _id, _id, img)

        s += """<ul id="aggregation-node-%s" style="display: %s; ">""" % (_id, display)
        # If we got no parents, no need to print the expand icon
        if len(sons) > 0:
            for son in sons:
                sub_s = self.print_aggregation_tree(son, html_id)
                s += '<li class="no_list_style">%s</li>' % sub_s


        s += '<li class="no_list_style">'
        if path == '/' and len(services) > 0:
            s += """<span class="alert-small"> Others </span>"""
        s += '<ul style="margin-left: 0px;">'
        # Sort our services before print them
        services.sort(hst_srv_sort)
        for svc in services:
            s += '<li class="%s">' % svc.state.lower()
            s += """<span class='alert-small alert-%s' style="">%s</span> for <span style="">%s since %s</span>""" % (svc.state.lower(), svc.state, self.get_link(svc, short=True), self.print_duration(svc.last_state_change, just_duration=True, x_elts=2))
            for i in range(0, svc.business_impact-2):
                s += '<img alt="icon state" src="/static/images/star.png">'
            s += '</li>'
        s += "</ul></li>"

                
        s += "</ul>"
        #safe_print("Returning s:", s)
        return s

    

helper = Helper()
