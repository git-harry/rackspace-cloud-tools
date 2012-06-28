import sys
import cloudfiles
import gzip
import StringIO
import os
import argparse
import re


def format_filename(log_name):
    """Convert log object name to container name and file name.

Input
Log name:
MyContainer/2011/06/10/04/10c6bb6a9c704739c525bf5d0b2ce2b7.log.0.gz
Output
Container:
MyContainer
Filename:
2011061004-10c6bb6a9c704739c525bf5d0b2ce2b7.log.0.gz

"""
    names = log_name.partition('/')
    filename = names[2].replace('/', '', 3)
    filename = filename.replace('/', '-', 1)
    container = names[0]
    return container, filename


def cache_log(container, filename, data, directory):
    """Write object to file in directory specified."""
    try:
        os.makedirs('/'.join((directory, container)))
    except os.error:
        pass
    with open('/'.join((directory, container, filename)), 'wb') as f:
        f.write(data)


def generate_object_list(container, path_prefix="", mk=""):
    """Return a list of all files in the container that match the
specified prefix. If no prefix supplied all objects returned.

"""
    obj_list = []
    obj_list_temp = container.list_objects(prefix=path_prefix, marker=mk)
    while obj_list_temp:
        obj_list.extend(obj_list_temp)
        mk = obj_list[-1]
        obj_list_temp = container.list_objects(prefix=path_prefix, marker=mk)
    return obj_list


def list_logs(log_container, search_term, num_files=0, start="", end=""):
    """List log objects.

Search term must end with a '/'

"""
    first = ''.join((search_term, start))
    
    obj_list = generate_object_list(log_container, path_prefix=search_term,
                                    mk=first)
    s = len(search_term)
    e = len(end)
    last = ''
    if end:
        for obj in obj_list[::-1]:
            if end in obj[s:s + e]:
                last = obj
                break
        try:
            end_pos = obj_list.index(last) + 1
        except ValueError:
            end_pos = None
    else:
        end_pos = None
    date_filtered_list = obj_list[:end_pos]
    return date_filtered_list[-num_files:]


def get_logs(connection, container_search_term, cache=True, num_files=0,
             start_date='', end_date='', directory="DownloadedLogFiles"):
    """ Download log files for a container and cat them.

cache=True controls whether or not the logs are cached not if the cache is
read. The cache is always read.
num_files is integer specifying number of files to download. The most
recent file is num_files=1, if num_files is not specified or 0 all files
downloaded
start_date and end_date can be used to filter the logs. num_files is
applied after the date filtering.

"""
    log_object_prefix = "".join((container_search_term, '/'))
    logs_container_name = ".CDN_ACCESS_LOGS"
    try:
        logs_container = connection.get_container(logs_container_name)
        log_list = list_logs(logs_container, log_object_prefix, num_files,
                             start_date, end_date)
        data = []
        for log in log_list:
            container, filename = format_filename(log)
            try:
                file_path = (directory, container, filename)
                with open('/'.join(file_path), 'rb') as f:
                    log_gz = f.read()
            except IOError:
                log_gz = logs_container.get_object(log).read()
                if cache:
                    cache_log(container, filename, log_gz, directory)
            log_gz_fobj = StringIO.StringIO(log_gz)
            #with gzip.GzipFile(fileobj=log_gz_fobj, mode='rb') as log_file:
            #    log_data = log_file.read()
            log_file = gzip.GzipFile(fileobj=log_gz_fobj, mode='rb')
            log_data = log_file.read()
            log_file.close()
            data.append(log_data)
        data_string = ''.join(data)
        return data_string
    except cloudfiles.errors.NoSuchContainer:
        print "Either logs aren't enabled or no logs have been generated yet."

def analyse(logs):
    #Provides summary report
    #log format:
    #IP_ADDRESS - - [DAY/MONTH/YEAR:HOUR:MINUTE:SECOND +TIMEZONE] "VERB /CONTAINER_HOSTNAME/OBJECT_NAME HTTP_VERSION" HTTP_STATUS_CODE BYTES "-" "USER_AGENT"
    log_lines = logs.split('\n')
    log_data = []
    for line in log_lines:
        try:
            re_str = r'(\S*) - - \[(.*?)\] "(\S*) (\S*) (\S*?)" ([0-9]*) ([0-9]*) "-" "(.*?)"'
            parts = re.match(re_str, line).groups()
        except AttributeError:
            continue
        data = {'ip_addr': parts[0]}
        (ip_addr, date_time, verb, obj, http_ver, status, bytes, user_agent) = parts
        data = {'ip_addr': ip_addr, 'date_time': date_time, 'verb': verb,
                'obj': obj, 'http_ver': http_ver, 'status': status,
                'bytes': bytes, 'user_agent': user_agent}
        log_data.append(data)
    
    uniq_ip_counts = {}
    uniq_obj_counts = {}
    total_bytes_downloaded = 0
    for line in log_data:
        uniq_ip_counts[line['ip_addr']] = uniq_ip_counts.get(line['ip_addr'], 0) + 1
        uniq_obj_counts[line['obj']] = uniq_obj_counts.get(line['obj'], 0) + 1
        total_bytes_downloaded += int(line['bytes'])
    uniq_ip_counts_list = uniq_ip_counts.items()
    uniq_ip_counts_list.sort(key=lambda x: x[1], reverse=True)
    uniq_obj_counts_list = uniq_obj_counts.items()
    uniq_obj_counts_list.sort(key=lambda x: x[1], reverse=True)

    output = []
    output.append('The total number of download requests is {0}'.format(len(log_data)))
    output.append('The number of unique IP addresses is {0}'.format(len(uniq_ip_counts)))
    output.append('The number of unique objects is {0}'.format(len(uniq_obj_counts)))
    data_dl_str = 'The total amount of data downloaded is {0:.1f} GB'
    output.append(data_dl_str.format(total_bytes_downloaded / 1073741824.0))
    obj_count_strings = ['\t'.join((x[0], str(x[1]))) for x in uniq_obj_counts_list[:10]]
    pop_obj_str = 'The top {0} most popular objects are:\n{1}'
    output.append(pop_obj_str.format(len(uniq_obj_counts_list[:10]), '\n'.join(obj_count_strings)))
    ip_count_strings = ['\t'.join((x[0], str(x[1]))) for x in uniq_ip_counts_list[:10]]
    freq_dl_str = 'The top {0} most frequent downloaders are:\n{1}'
    output.append(freq_dl_str.format(len(uniq_ip_counts_list[:10]), '\n'.join(ip_count_strings)))
    return '\n'.join(output)


def cmd_parser(parser_class, line=sys.argv[1:], prog_name=sys.argv[0]):
    """Provide commandline interface for get_logs."""
    parser = parser_class(description='Display container CDN logs.',
                          prog=prog_name)

    parser.add_argument('username')
    parser.add_argument('apikey')
    parser.add_argument('region')

    parser.add_argument('container',
                        help='name of CDN and log enabled container')
    # counter-intuitively if nocache is True, caching will be used.
    parser.add_argument('--nocache', default=True, action='store_false',
                        help='cache logs on local machine.')
    parser.add_argument(
        '--num_files',
        default=0,
        type=int,
        help='number of log files to display, starting with the most recent.')
    parser.add_argument('--start_date', default='', metavar='YYYY/MM/DD/HH',
                        help='display logs newer than date specified.')
    parser.add_argument('--end_date', default='', metavar='YYYY/MM/DD/HH',
                        help='display logs older than date specified.')
    parser.add_argument('--analyse', '--analyze', default=False, action='store_true',
                        help='provide analysis summary.')
    parser.add_argument('--snet', default=False, action='store_true',
                        help='uses servicenet to prevent bandwidth charges.')
    args = parser.parse_args(line)
    def open_connection(username, api_key, region, snet):
        if region.upper() == "UK":
            auth_url = cloudfiles.consts.uk_authurl
        else:
            auth_url = cloudfiles.consts.us_authurl
        conn = cloudfiles.get_connection(username,
                                         api_key,
                                         authurl=auth_url,
                                         servicenet=snet)
        return conn

    conx = open_connection(args.username, args.apikey, args.region, args.snet)
    
    logs =  get_logs(conx, args.container, args.nocache, args.num_files,
                   args.start_date, args.end_date)
    if args.analyse:
        print analyse(logs)
    else:
        print logs

if __name__ == '__main__':

    cmd_parser(argparse.ArgumentParser)
