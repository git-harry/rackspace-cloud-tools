"""Assume /proc/net/dev only changes on reboot."""

import re
import os
import datetime
import time
import sys
import smtplib
import subprocess


class BandwidthTracker(object):

    def __init__(self, config_file='/etc/cs_bandwidth_tracker.conf'):
        self.config_file = config_file
        conf = self.load_config()

        self.log_dir = '/var/log/cs_bandwidth_tracker'
        try:
            os.mkdir(self.log_dir, 755)
        except OSError:
            pass
        self.log_name_prefix = '/'.join((self.log_dir, 'data'))
        self.limits_log_name_prefix = '/'.join((self.log_dir, 'limits'))
        self.time_fmt = '%Y%m%d-%H:%M:%S'

        try:
            self.interface = conf['interface'].strip()
            bd = conf['billing_date'].strip()
            if len(bd) == 1:
                bd = ''.join(('0', bd))
            if len(bd) == 2:
                self.start_billing = bd
            else:
                print 'Error: You must set the billing_date.'
                sys.exit()
            action = [(item[0].split('_', 2), item[1])
                       for item in conf.items() if item[0][:7] == 'action_']
            self.action = {}
            for a in action:
                if len(a[0]) > 2:
                    try:
                        self.action['_'.join(a[0][:2])][a[0][2]] = a[1]
                    except KeyError:
                        self.action['_'.join(a[0][:2])] = {}
                        self.action['_'.join(a[0][:2])][a[0][2]] = a[1]
                else:
                    self.action['_'.join(a[0][:2])] = a[1]

            self.limits = {'receive': {}, 'transmit': {}}
            self.limits['receive'] = dict([(item[0][14:], item[1])
                                            for item in conf.items()
                                            if item[0][:14] == 'limit_receive_'])
            self.limits['transmit'] = dict([(item[0][15:], item[1])
                                             for item in conf.items()
                                             if item[0][:15] == 'limit_transmit_'])
        except KeyError, e:
            print 'Config file attribute', e, 'isn\'t configured.'
            sys.exit()

    def load_config(self):
        try:
            fc = open(self.config_file, 'ro')
            conf_data = fc.readlines()
        finally:
            fc.close()
        config = {}
        for line in conf_data:
            if line[0] == '#' or line == '\n':
                continue
            params = re.match(r'(\w*) = (.*)', line)
            config[params.group(1)] = params.group(2)

        return config

    def get_new_data(self):
        try:
            fr = open('/proc/net/dev', 'ro')
            raw_data = fr.readlines()
        finally:
            fr.close()

        for line in raw_data:
            search_string = r'\s*%s:' % self.interface
            if re.match(search_string, line):
                line = line.strip('\n')
                usage = [l for l in line.split(' ') if l]
                if len(usage) == 16:
                    usage = usage[0].split(':') + usage[1:]
                break
        #assuming eth0 exists and only one line matches
        time = datetime.datetime.now()
        data = [time, usage]
        return data

    def get_last_data(self, log_name):
        # must be called before new data logged
	try:
	    f = open(log_name, 'ro')
	    while True:
		line = f.readline()
		if line:
	            last_data = line
		else:
		    data = [l for l in last_data.split(' ') if l]
		    break
	finally:
	    try:
		f.close()
	    except UnboundLocalError:
		return None

	return [datetime.datetime(*(time.strptime(data[0], self.time_fmt)[0:6])), data[1:]]

    def get_boot_time(self):
        try:
            fr = open('/proc/stat', 'ro')
            raw_data = fr.readlines()
        finally:
            fr.close()
        for line in raw_data:
            search_string = r'btime ([0-9]*)'
            matches = re.match(search_string, line)
            if matches:
                boot_time_epoch = matches.group(1)
                break
        return datetime.datetime.fromtimestamp(float(boot_time_epoch))

    def calculate_total(self, new_data, previous_data, boot_time, billing_date):

        try:
            total_data = ['total:']
            new_int = new_data[1][1:17]
            prev_int = previous_data[1][1:17]
            prev_total = previous_data[1][18:-1]

            new_and_old = zip(new_int, prev_int, prev_total)

            if boot_time < previous_data[0]:
                for each in new_and_old:
                    if int(each[0]) < int(each[1]):
                        #the interface must have been shutdown
                        total_data = ['total:']
                        for each in new_and_old:
                            total_data.append(str(int(each[0]) + int(each[2])))
                        break
                    else:
                        total_data.append(str(int(each[0]) - int(each[1]) + int(each[2])))
            else:
                # if the server has been rebooted before the end of the month
                for each in new_and_old:
                    total_data.append(str(int(each[0]) + int(each[2])))
        except TypeError:
            # no previous data
            if boot_time < billing_date:
                total_data.extend(16 * ['0'])
            else:
                total_data.extend(new_int)

        new_data[1].extend(total_data)
        return new_data

    def get_billing_period(self, date_now):

        td_string = date_now.strftime(self.time_fmt)
        td_string = ''.join((td_string[:6],
                             self.start_billing,
                             td_string[8:]))

        def date_fixer(date_string):
            try:
                test_date = datetime.datetime(*(time.strptime(date_string, self.time_fmt)[0:6]))
            except ValueError:
                # assumes ValueError generated by day being out range for month
                if date_string[4:6] in ('04', '06', '09', '11'):
                    date_string = ''.join((date_string[:6], '30', date_string[8:]))
                elif int(date_string[:4]) % 4 == 0:
                    date_string = ''.join((date_string[:6], '29', date_string[8:]))
                else:
                    date_string = ''.join((date_string[:6], '28', date_string[8:]))
                test_date = datetime.datetime(*(time.strptime(date_string, self.time_fmt)[0:6]))

            return test_date, date_string

        test_date, td_string = date_fixer(td_string)

        if date_now < test_date:
            if date_now.month == 1:
                month = '12'
                year = str(date_now.year - 1)
            else:
                month = str(date_now.month - 1)
                if len(month) < 2:
                    month = ''.join(('0', month))
                year = str(date_now.year)
            td_string = ''.join((year,
                                 month,
                                 self.start_billing,
                                 td_string[8:]))
        billing_date, billing_string = date_fixer(td_string)

        self.billing_date = billing_date
        return billing_date

    def log_data(self, data, log_name):
        data_string_list = [data[0].strftime(self.time_fmt)]
        data_string_list.extend(data[1])
        data_string_list.append('\n')
        new_entry = ' '.join(data_string_list)
        try:
            fa = open(log_name, 'a')
            fa.write(new_entry)
        finally:
            fa.close()

    def limits_test(self, new_data, limits_log_name):
        receive_labels = ('bytes', 'packets', 'errs', 'drop', 'fifo', 'frame',
                          'compressed', 'multicast')
        transmit_labels = ('bytes', 'packets', 'errs', 'drop', 'fifo colls',
                           'carrier', 'compressed')
        receive_data = new_data[1][18:26]
        transmit_data = new_data[1][26:]
        receive = dict(zip(receive_labels, receive_data))
        transmit = dict(zip(transmit_labels, transmit_data))
        data = dict((('receive', receive), ('transmit', transmit)))
        limits_exceeded = {}
        for direction, limits in self.limits.iteritems():
            for limit, value in limits.iteritems():
                if int(value) < int(data[direction][limit]):
                    name = '_'.join(('limit', direction, limit))
                    limits_exceeded[name] = (value, data[direction][limit])
        limit_log = []
        try:
            try:
                fl = open(limits_log_name, 'ro')
                limit_log_data = fl.readlines()
                limit_log = [line.split() for line in limit_log_data]
            finally:
                try:
                    fl.close()
                except UnboundLocalError:
                    pass
        except IOError:
            pass
        for limit in limit_log:
            try:
                if int(limits_exceeded[limit[1]][0]) <= int(limit[3]):
                    del limits_exceeded[limit[1]]
            except KeyError:
                pass
        new_limit_log_data = []
        for limit in limits_exceeded.iteritems():
            line = ' '.join((new_data[0].strftime(self.time_fmt), limit[0], '=', limit[1][0], '; current =', limit[1][1], '\n'))
            new_limit_log_data.append(line)
        try:
            f = open(limits_log_name, 'a')
            f.write(''.join(new_limit_log_data))
        finally:
            f.close()
        return limits_exceeded

    def action_run(self, limits):
        if limits:
            for func, params in self.action.iteritems():
                kwargs = {}
                try:
                    kwargs = params.copy()
                except AttributeError:
                    kwargs['param'] = params
                kwargs['limits'] = limits

                getattr(self, func)(**kwargs)

    def action_email(self, **params):
        limits_table = 'Name\t\tLimit\t\tCurrent Value'
        for k, v in params['limits'].iteritems():
            line = '\t\t'.join((k, v[0], v[1]))
            limits_table = '\r\n'.join((limits_table, line))
        msg = 'From: %s\r\nTo: %s\r\nSubject: Bandwidth Tracker Alert\r\n\r\nTake a look!\r\n%s' % (params['sender'], params['recipient'], limits_table)
	server = smtplib.SMTP()
        server.connect(params['host'], params['port'])
        server.ehlo()
	server.starttls()
        server.ehlo()
        server.login(params['username'], params['password'])

        server.sendmail(params['sender'], params['recipient'], msg)
        server.quit()

    def action_ifdown(self, **params):
        if params['param'] == 'True':
            subprocess.call(('ifdown', self.interface))


if __name__ == '__main__':

    tracker = BandwidthTracker()
    nd = tracker.get_new_data()
    billing_date = tracker.get_billing_period(nd[0])
    log_name = '-'.join((tracker.log_name_prefix, billing_date.strftime('%Y%m%d')))
    limits_log_name = '-'.join((tracker.limits_log_name_prefix, billing_date.strftime('%Y%m%d')))
    od = tracker.get_last_data(log_name)
    bt = tracker.get_boot_time()
    nd = tracker.calculate_total(nd, od, bt, billing_date)
    tracker.log_data(nd, log_name)
    lt = tracker.limits_test(nd, limits_log_name)
    tracker.action_run(lt)
