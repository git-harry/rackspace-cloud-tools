#   Copyright 2012 git-harry
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import datetime
import novaclient.exceptions
import novaclient.v1_1
import os
import smtplib
import sys
import time
import traceback

from email.mime.text import MIMEText

os.environ['NOVA_RAX_AUTH'] = 'True'

regions = {'UK': 'https://lon.auth.api.rackspacecloud.com/v2.0',
           'US': 'https://auth.api.rackspacecloud.com/v2.0'}


def get_schedule(filename):
    '''file is list of instance id's
       todo: check each instance id appears only once'''
    with open(filename) as f:
        data = f.readlines()
        data_set = set([d.strip() for d in data])
        img_reqs = []
        for val in data_set:
            img_req = {'complete': False, 'check': 0, 'current': None}
            img_req['instance_id'] = val
            img_reqs.append(img_req)
    return tuple(img_reqs)


def start_imaging(img_reqs, shed_type):
    for req in img_reqs:
        req_name = '{0}-{1}-{2}'.format('shed', shed_type, req['instance_id'])
        try:
            req['image_id'] = c.servers.create_image(req['instance_id'],
                                                     req_name)
        except (novaclient.exceptions.ClientException) as e:
            req['image_id'] = None
            req['failed'] = (e.code, e.message)
    return img_reqs


def check_status(img_reqs):
    img_lst = c.images.list()
    for req in [req for req in img_reqs if not
                req['complete'] and
                'failed' not in req]:
        try:
            req['current'] = c.images.get(req['image_id'])
            req['check'] = req['check'] - 1 or 0
        except novaclient.exceptions.ClientException as e:
            req['check'] += 1
            if req['check'] == 3:
                req['failed'] = (e.code, e.message)
            continue
        to_delete = []
        if req['current'].status != 'ACTIVE':
            continue
        #delete all but the newest
        ims = [img for img in img_lst if img.name == req['current'].name]
        ims.sort(key=lambda x:
                 datetime.datetime.strptime(x.created, '%Y-%m-%dT%H:%M:%SZ'))
        to_delete = ims[:-1]
        for img in to_delete:
            img.delete()
        req['complete'] = True
    return img_reqs


def load_config(conf_file):
    with open(conf_file) as f:
        conf_data = f.readlines()
    params = {}
    for line in conf_data:
        if line.startswith('#'):
            continue
        try:
            k1, v1 = line.split('_', 1)
            k2, v2 = v1.split('=', 1)
        except ValueError:
            continue
        params.setdefault(k1.strip(), {})[k2.strip()] = v2.strip()
    return params


def send_email(msg_txt, e):
    msg = MIMEText(msg_txt)
    msg['Subject'] = 'Scheduled image alert'
    msg['From'] = e['sender']
    msg['To'] = e['recipient']
    server = smtplib.SMTP()
    server.connect(e['host'], e['port'])
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(e['username'], e['password'])
    server.sendmail(e['sender'], e['recipient'], msg.as_string())
    server.quit()


if __name__ == '__main__':
    try:
        #shed_type should be daily or weekly
        shed_type = sys.argv[1]
        conf_file = sys.argv[2]
        params = load_config(conf_file)
        username = params['cs']['username']
        api_key = params['cs']['api_key']
        region = params['cs']['region']
        c = novaclient.v1_1.client.Client(username,
                                          api_key,
                                          project_id=0,
                                          auth_url=regions[region])
        try:
            servers_list_filename = params['servers']['list']
        except KeyError:
            raise Exception('servers_list parameter missing from conf file.')
        else:
            img_reqs = get_schedule(servers_list_filename)
        img_reqs = start_imaging(img_reqs, shed_type)

        start_time = datetime.datetime.utcnow()
        current_time = datetime.datetime.utcnow()
        timeout = datetime.timedelta(hours=4)

        not_complete = True
        while not_complete and current_time - start_time < timeout:
            time.sleep(300)
            img_reqs = check_status(img_reqs)
            current_time = datetime.datetime.utcnow()
            if not [img for img in img_reqs if not
                img['complete'] and
                'failed' not in img]:
                not_complete = False

        outstanding = [img for img in img_reqs if not img['complete']]
        alert_lines = []
        for img in outstanding:
            try:
                line_temp = ('{instance_id} - {image_id} -'
                             ' {current.status} - {current.progress}')
                line = line_temp.format(**img)
            except AttributeError:
                line_temp = '{instance_id} - {failed[0]} - {failed[1]}'
                line = line_temp.format(**img)
            alert_lines.append(line)
        time_now = datetime.datetime.utcnow()
        l0 = ' '.join((time_now.strftime('%Y-%m-%d %H:%M:%S'), 'UTC'))
        l1 = '****Failed****'
        l2 = '\n'.join(alert_lines) or 'None'
        l3 = '****Active****'
        c = []
        for img in img_reqs:
            if img['complete']:
                c.append('\t'.join((img['instance_id'],
                                    img['current'].id,
                                    img['current'].status)))
        l4 = '\n'.join(c)
        txt = '\n'.join((l0, l1, l2, l3, l4, '\n'))
        try:
            log_file_name = params['log']['filename']
        except KeyError:
            pass
        else:
            with open(log_file_name, 'a') as f:
                f.write(txt)
        try:
            em = params['email']
        except KeyError:
            pass
        else:
            send_email(txt, em)
    except Exception as e:
        try:
            log_file_name = params['log']['filename']
        except KeyError:
            raise e
        else:
            with open(log_file_name, 'a') as f:
                f.write('********Program Failure********\n')
                traceback.print_exc(file=f)
