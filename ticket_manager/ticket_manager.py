'''If ticket creation/update fails check in the cloud control panel to see if that works.'''
import urllib
import urllib2
import pycurl
import StringIO
import cookielib
import re
import json
import sys

class tickets(object):
    def __init__(self, username, password, region):
        regions = {'UK': 'lon.manage.rackspacecloud.com',
                   'US': 'manage.rackspacecloud.com'}
        self.hostname = regions[region]
        self.cj = cookielib.MozillaCookieJar()
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cj))
        urllib2.install_opener(self.opener)
        params = {'username': username, 'password': password}
        params_string = urllib.urlencode(params)
        url = ''.join(('https://', self.hostname, '/Login.do'))
        req = urllib2.Request(url, data=params_string)
        self.opener.open(req)

    def _parse_ticket_list(self, url):
        p = self.opener.open(url)
        page = p.read()
        try:
            raw_data = re.search(r'\\"rows\\":\[\[.*', page).group(0)[9:-3]
        except AttributeError:
            raw_data = '[]'
        json_data = raw_data.replace(r'\"', '"')
        return json.loads(json_data)


    def list_all(self):
        url = ''.join(('https://', self.hostname, '/Tickets/AllTickets.do'))
        ticket_list = self._parse_ticket_list(url)
        tickets = []
        for t in ticket_list:
            ticket = {}
            ticket['subject'] = t[1][0]
            ticket['status'] = t[2]
            ticket['number'] = t[3][0]
            ticket['owner'] = t[4]
            ticket['created'] = t[5]
            ticket['updated'] = t[6]
            tickets.append(ticket)
        return tickets

    def list_open(self):
        url = ''.join(('https://', self.hostname, '/Tickets/YourTickets.do'))
        ticket_list = self._parse_ticket_list(url)
        tickets = []
        for t in ticket_list:
            ticket = {}
            ticket['subject'] = t[1][0]
            ticket['status'] = t[2]
            ticket['number'] = t[3][0]
            ticket['created'] = t[4]
            ticket['updated'] = t[5]
            tickets.append(ticket)
        return tickets

    def list_closed(self):
        url = ''.join(('https://', self.hostname, '/Tickets/ClosedTickets.do'))
        ticket_list = self._parse_ticket_list(url)
        tickets = []
        for t in ticket_list:
            ticket = {}
            ticket['subject'] = t[1][0]
            ticket['status'] = t[2]
            ticket['number'] = t[3][0]
            ticket['created'] = t[4]
            ticket['updated'] = t[5]
            tickets.append(ticket)
        return tickets

    def get_ticket(self, ticket_id):
        url = ''.join(('https://', self.hostname, '/Tickets/ViewTicket.do', '?ticketId=', ticket_id))
        p = self.opener.open(url)
        page = p.read()
        tkt = {}
        try:
            raw_info = re.search(r'<h2 id="topSection">Ticket Info</h2>[\s\S]*<div id="ticketButtons">', page).group(0)
        except AttributeError:
                raise Exception(re.search(r'\s*<div class="msgBoxError">\s*([\s\S]*?)\s+</div>', page).group(1))
        raw_info_1 = re.findall(r'>(.*)</td>', raw_info)
        raw_info_list = [info for info in raw_info_1 if info != '&nbsp;']
        raw_info_dict = dict(zip(raw_info_list[1::2], raw_info_list[2::2]))
        tkt['updated'] = raw_info_dict.get('Updated', '')
        tkt['created'] = raw_info_dict.get('Created', '')
        tkt['subject'] = raw_info_dict.get('Subject', '')
        tkt['product'] = raw_info_dict.get('Product', '')
        tkt['category'] = raw_info_dict.get('Category', '')
        tkt['number'] = raw_info_dict.get('Ticket Number', '')
        tkt['details'] = raw_info_dict.get('Details', '')
        tkt['status'] = re.search(r'/img>[\s]*(.*)<br/>', raw_info).group(1)
        raw_comments = re.findall(r'<span class="comment-author">\s*(.*)\s*said\.\.\.\s*</span>\s*<span class="comment-time">(.*)</span>\s*</div>\s*</div>\s*<div class="comment-content">\s*<pre>([\s\S\n]*?)</pre>', page)
        comments = []
        for raw_comment in raw_comments:
            comment = {}
            comment['author'] = raw_comment[0]
            comment['created'] = raw_comment[1]
            comment['details'] = raw_comment[2]
            comments.append(comment)
        tkt['comments'] = comments[::-1]
        return ticket(self.hostname, self.cj, **tkt)

    def create(self, subject, description, category, servername='', lbname='', attachment={}):
        return ticket(self.hostname, self.cj, subject=subject,
                      comments=[{'details': description, 'author': '', 'created': '', 'attachment': attachment}],
                      category=category, servername=servername, lbname=lbname)

class ticket(object):
    '''The current list of allowed categories is:
        cloud_servers:general_support
        cloud_servers:api
        cloud_servers:other
        cloud_files:general_support
        cloud_files:api
        cloud_files:cdn
        cloud_files:fm
        cloud_files:other
        account:billing
        account:cp
        account:other
        load_balancers:general_support
        load_balancers:api
        load_balancers:other
        cloud_databases:general_support
        cloud_databases:api
        cloud_databases:other 
    '''
    def __init__(self, hostname, session, **kwargs):
        self.session = re.search(r'(JSESSION\S*)', str(session)).group(0)
        self.hostname = hostname
        self.updated = kwargs.get('updated', '')
        self.created = kwargs.get('created', '')
        self.subject = kwargs.get('subject', '')
        self.product = kwargs.get('product', '')
        self.category = kwargs.get('category', '')
        self.number = kwargs.get('number', '')
        self.status = kwargs.get('status', '')
        self.details = kwargs.get('details', '')
        self.comments = kwargs.get('comments', [])
        self.servername = kwargs.get('servername', '')
        self.lbname = kwargs.get('lbname', '')

    def __str__(self):
        up = ': '.join(('Updated', self.updated))
        cr = ': '.join(('Created', self.created))
        su = ': '.join(('Subject', self.subject))
        pr = ': '.join(('Product', self.product))
        ca = ': '.join(('Category', self.category))
        nu = ': '.join(('Ticket Number', self.number))
        st = ': '.join(('Status', self.status))
        de = ': '.join(('Details', self.details))
        coms = ''
        for comment in self.comments:
            com = ''.join(('Updated by ', comment['author'], ' on ', comment['created'], '\n', comment['details']))
            coms = '\n'.join((coms, com))
        co = ':\n'.join(('Comments', coms))
        return '\n'.join((nu, su, st, cr, up, ca, pr, de, co))

    def submit(self):
        #only adds the newest comment
        comment = self.comments[-1]
        if self.number:
            url = ''.join(('https://', self.hostname, '/tickets/AddComment.do'))
            parts = [('ticketId', self.number), ('commentText',comment['details'])]
        else:
            url = ''.join(('https://', self.hostname, '/Tickets/SaveTicket.do'))
            parts = [('siteID', ''), ('euID', ''), ('isThisAClientTicket', ''),
                     ('subject', self.subject), ('description', comment['details']),
                     ('category', self.category), ('siteName', ''),
                     ('serverName', self.servername), ('loadBalancerName', self.lbname)]
        conn = pycurl.Curl()
        #never tested because attachments are broken in the control panel
        if comment['attachment']:
            parts.append(('attachment', (conn.FORM_FILE, comment['attachment']['filename'], conn.FORM_CONTENTTYPE, comment['attachment']['contenttype'])))
        #httplib doesn't handle 100 Continue properly so using pycurl
        conn.setopt(pycurl.URL, url)
        conn.setopt(pycurl.HTTPHEADER, [': '.join(('Cookie', self.session))])
        conn.setopt(pycurl.HTTPPOST, parts)
        resp = StringIO.StringIO()
        conn.setopt(pycurl.WRITEFUNCTION, resp.write)
        conn.perform()
        status = conn.getinfo(pycurl.HTTP_CODE)
        conn.close()
        if status is 200:
            try:
                number = re.search(r'Ticket #([0-9]+)', resp.getvalue()).group(1)
                if not self.number:
                    self.number = number
            except AttributeError:
                raise Exception(re.search(r'\s*<div class="msgBoxError">\s*([\s\S]*?)\s+</div>', resp.getvalue()).group(1))
        else:
            raise Exception('Failed to submit ticket {0}. HTTP status code: {1}'.format(self.number, status))

    def add_comment(self, description, attachment={}):
        self.comments.append({'details': description, 'author': '', 'created': '', 'attachment': attachment})


