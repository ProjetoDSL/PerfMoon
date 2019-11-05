# Author: Girardon <ggirardon@gmail.com> and Victor <victorsc_rs@gmail.com>
# Last Change: Nov 05, 2019

import logging
import os
import re

from bs4 import BeautifulSoup
from humanfriendly import compact, concatenate, format_size, format_timespan, pluralize, Timer
from proc.apache import find_apache_memory_usage, find_apache_workers
from proc.core import Process
from property_manager import (
    PropertyManager,
    cached_property,
    lazy_property,
    mutable_property,
    required_property,
    writable_property,
)
from six.moves.urllib.error import HTTPError
from six.moves.urllib.request import urlopen

from perf_moon.exceptions import AddressDiscoveryError, StatusPageError

__version__ = '0.2'
__all__ = (
    'HANGING_WORKER_THRESHOLD',
    'IDLE_MODES',
    'NATIVE_WORKERS_LABEL',
    'PORTS_CONF',
    'STATUS_COLUMNS',
    'ApacheManager',
    'KillableWorker',
    'NetworkAddress',
    'NonNativeWorker',
    'WorkerStatus',
)

PORTS_CONF = '/etc/apache2/ports.conf'

STATUS_COLUMNS = (
    'Srv', 'PID', 'Acc', 'M', 'CPU', 'SS', 'Req', 'Conn', 'Child', 'Slot',
    'Client', 'VHost', 'Request',
)

IDLE_MODES = ('_', 'I', '.')

NATIVE_WORKERS_LABEL = 'native'

HANGING_WORKER_THRESHOLD = 60 * 5
logger = logging.getLogger(__name__)


class ApacheManager(PropertyManager):

    def __init__(self, *args, **kw):
        if args:
            args = list(args)
            kw['ports_config'] = args.pop(0)
        super(ApacheManager, self).__init__(*args, **kw)

    @writable_property
    def num_killed_active(self):
        return 0

    @writable_property
    def num_killed_idle(self):
        return 0

    @writable_property
    def status_response(self):
        return None

    @mutable_property
    def ports_config(self):
        return PORTS_CONF

    @cached_property
    def listen_addresses(self):
        
        logger.debug("Discovering where Apache is listening by parsing %s ..", self.ports_config)
        
        if not os.path.isfile(self.ports_config):
            raise AddressDiscoveryError(compact("""Failed!""", filename=self.ports_config))
        matched_addresses = []
        pattern = re.compile(r'^(.+):(\d+)$')
        with open(self.ports_config) as handle:
            for lnum, line in enumerate(handle, start=1):
                tokens = line.split()
                if len(tokens) >= 2 and tokens[0] == 'Listen':
                    parsed_value = None
                    if tokens[1].isdigit():
                        parsed_value = NetworkAddress(port=int(tokens[1]))
                    else:
                        match = pattern.match(tokens[1])
                        if match:
                            address = match.group(1)
                            port = int(match.group(2))
                            if address == '0.0.0.0':
                                address = '127.0.0.1'
                            parsed_value = NetworkAddress(address=address, port=port)
                    if parsed_value is not None:
                        if len(tokens) >= 3:
                            parsed_value.protocol = tokens[2]
                        logger.debug("Parsed listen directive on line %i: %s", lnum, parsed_value)
                        matched_addresses.append(parsed_value)
                    else:
                        logger.warning("Failed to parse listen directive on line %i: %s", lnum, line)
        if not matched_addresses:
            raise AddressDiscoveryError(compact("""
                Failed to discover any addresses or ports that Apache is
                listening on! Maybe I'm parsing the wrong configuration file?
                ({filename})
            """, filename=self.ports_config))
        logger.debug("Discovered %s that Apache is listening on: %s",
                     pluralize(len(matched_addresses), "address", "addresses"),
                     concatenate(map(str, matched_addresses)))
        return matched_addresses

    @cached_property(writable=True)
    def html_status_url(self):
        status_url = "%s/server-status" % self.listen_addresses[0].url
        logger.debug("Discovered Apache HTML status page URL: %s", status_url)
        return status_url

    @cached_property
    def text_status_url(self):
        status_url = "%s?auto" % self.html_status_url
        logger.debug("Discovered Apache plain text status page URL: %s", status_url)
        return status_url

    @cached_property
    def html_status(self):
        return self.fetch_status_page(self.html_status_url)

    @cached_property
    def text_status(self):
        return self.fetch_status_page(self.text_status_url).decode()

    def fetch_status_page(self, status_url):
        timer = Timer()
        logger.debug("Fetching Apache status page from %s ..", status_url)
        try:
            response = urlopen(status_url)
        except HTTPError as e:
            response = e
        response_code = response.getcode()
        if response_code != 200:
            self.status_response = False
            raise StatusPageError(compact("""
                Failed to retrieve Apache status page from {url}! Expected to
                get HTTP response status 200, got {code} instead.
            """, url=status_url, code=response_code))
        response_body = response.read()
        logger.debug("Fetched %s in %s.", format_size(len(response_body)), timer)
        self.status_response = True
        return response_body

    @cached_property
    def slots(self):
        soup = BeautifulSoup(self.html_status, "html.parser")
        required_columns = [normalize_text(c) for c in STATUS_COLUMNS]
        for table in soup.findAll('table'):
            matched_rows = list(parse_status_table(table))
            validated_rows = [r for r in matched_rows if all(c in r for c in required_columns)]
            if validated_rows:
                return [WorkerStatus(status_fields=f) for f in validated_rows]
        raise StatusPageError(compact("""
            Failed to parse Apache status page! No tables found containing all
            of the required column headings and at least one row of data that
            could be parsed.
        """))

    @cached_property
    def workers(self):
        return [ws for ws in self.slots if ws.m != '.']

    @cached_property
    def hanging_workers(self):
        return [ws for ws in self.workers if ws.is_active and ws.ss >= HANGING_WORKER_THRESHOLD]

    @cached_property
    def killable_workers(self):
        all_workers = list(self.workers)
        native_pids = set(w.pid for w in self.workers)
        for process in find_apache_workers():
            if process.pid not in native_pids:
                all_workers.append(NonNativeWorker(process=process))
        return sorted(all_workers, key=lambda p: p.pid)

    @property
    def manager_metrics(self):
        return dict(workers_hanging=len(self.hanging_workers),
                    workers_killed_active=self.num_killed_active,
                    workers_killed_idle=self.num_killed_idle,
                    status_response=self.status_response)

    @cached_property
    def server_metrics(self):
        logger.debug("Extracting metrics from Apache's plain text status page ..")
        return dict(
            # Example: "Total Accesses: 49038"
            total_accesses=int(self.extract_metric(r'^Total Accesses: (\d+)')),
            # Example: "Total kBytes: 169318"
            total_traffic=int(self.extract_metric(r'^Total KBytes: (\d+)')) * 1024,
            # Example: "CPULoad: 7.03642"
            cpu_load=float(self.extract_metric(r'^CPULoad: ([0-9.]+)')),
            # Example: "Uptime: 85017"
            uptime=int(self.extract_metric(r'^Uptime: (\d+)')),
            # Example: "ReqPerSec: .576802"
            requests_per_second=float(self.extract_metric(r'^ReqPerSec: ([0-9.]+)')),
            # Example: "BytesPerSec: 2039.38"
            bytes_per_second=float(self.extract_metric(r'^BytesPerSec: ([0-9.]+)')),
            # Example: "BytesPerReq: 3535.66"
            bytes_per_request=float(self.extract_metric(r'^BytesPerReq: ([0-9.]+)')),
            # Example: "BusyWorkers: 2"
            busy_workers=int(self.extract_metric(r'^BusyWorkers: (\d+)')),
            # Example: "IdleWorkers: 6"
            idle_workers=int(self.extract_metric(r'^IdleWorkers: (\d+)')),
        )

    def extract_metric(self, pattern, default='0'):
        modified_pattern = re.sub(r'\s+', r'\s+', pattern)
        match = re.search(modified_pattern, self.text_status, re.IGNORECASE | re.MULTILINE)
        if match:
            logger.debug("Pattern '%s' matched '%s'.", pattern, match.group(0))
            return match.group(1)
        else:
            logger.warning("Pattern %r didn't match plain text Apache status page contents!", pattern)
            return default

    @cached_property
    def memory_usage(self):
        return self.combined_memory_usage[0]

    @cached_property
    def wsgi_process_groups(self):
        return self.combined_memory_usage[1]

    @cached_property
    def combined_memory_usage(self):
        return find_apache_memory_usage()

    def kill_workers(self, max_memory_active=0, max_memory_idle=0, timeout=0, dry_run=False):
        killed = set()
        num_checked = 0
        for worker in self.killable_workers:
            if worker.pid not in killed:
                kill_worker = False
                memory_usage_threshold = max_memory_active if worker.is_active else max_memory_idle
                if memory_usage_threshold and worker.memory_usage > memory_usage_threshold:
                    logger.info("Killing %s using %s (%s) ..",
                                worker, format_size(worker.memory_usage),
                                worker.request or 'last request unknown')
                    kill_worker = True
                elif timeout and worker.is_active and getattr(worker, 'ss', 0) > timeout:
                    logger.info("Killing %s hanging for %s since last request (%s) ..",
                                worker, format_timespan(worker.ss),
                                worker.request or 'unknown')
                    kill_worker = True
                if kill_worker:
                    if not dry_run:
                        worker.process.kill()
                    killed.add(worker.pid)
                    if worker.is_active:
                        self.num_killed_active += 1
                    else:
                        self.num_killed_idle += 1
            num_checked += 1
        if killed:
            logger.info("Killed %i of %s.", len(killed), pluralize(num_checked, "Apache worker"))
        else:
            logger.info("No Apache workers killed (found %s within resource usage limits).",
                        pluralize(num_checked, "worker"))
        return list(killed)

    def save_metrics(self, data_file):
        
        if data_file == '-':
            logger.debug("Reporting metrics on standard output ..")
        else:
            logger.debug("Storing metrics in %s ..", data_file)
        output = ['# Global Apache server metrics.']
        for name, value in sorted(self.server_metrics.items()):
            output.append('%s\t%s' % (name.replace('_', '-'), value))
        output.extend(['', '# Metrics internal to perf-moon.'])
        for name, value in sorted(self.manager_metrics.items()):
            if isinstance(value, bool):
                value = 0 if value else 1
            output.append('%s\t%s' % (name.replace('_', '-'), value))
        groups = dict(self.wsgi_process_groups)
        ordered_group_names = [NATIVE_WORKERS_LABEL] + sorted(groups.keys())
        groups[NATIVE_WORKERS_LABEL] = self.memory_usage
        metric_names = ('count', 'min', 'max', 'average', 'median')
        for group_name in ordered_group_names:
            output.append('')
            if group_name == NATIVE_WORKERS_LABEL:
                output.append('# Memory usage of native Apache worker processes.')
            else:
                output.append('# Memory usage of %r WSGI worker processes.' % group_name)
            for metric in metric_names:
                output.append('\t'.join([
                    'memory-usage', group_name, metric, str(
                        len(groups[group_name]) if metric == 'count'
                        else getattr(groups[group_name], metric)
                    ),
                ]))
        if data_file == '-':
            print('\n'.join(output))
        else:
            temporary_file = '%s.tmp' % data_file
            with open(temporary_file, 'w') as handle:
                handle.write('\n'.join(output) + '\n')
            os.rename(temporary_file, data_file)

    def refresh(self):
        self.clear_cached_properties()


class NetworkAddress(PropertyManager):
    @property
    def url(self):
        tokens = [self.protocol, '://', self.address]
        if not ((self.protocol == 'http' and self.port == 80) or
                (self.protocol == 'https' and self.port == 443)):
            tokens.append(':%s' % self.port)
        return ''.join(tokens)

    @required_property
    def protocol(self):
        return 'https' if self.port == 443 else 'http'

    @required_property
    def address(self):
        return '127.0.0.1'

    @required_property
    def port(self):
        
    def __str__(self):
        return self.url


class KillableWorker(PropertyManager):

    @required_property
    def is_active(self):
        
    @property
    def is_alive(self):
        return self.process.is_alive if self.process else False

    @lazy_property
    def memory_usage(self):
        return self.process.rss if self.process else None

    @required_property
    def pid(self):
        return self.process.pid if self.process else None

    @mutable_property(cached=True)
    def process(self):
        return Process.from_pid(self.pid) if self.pid else None

    @mutable_property
    def request(self):
        

class NonNativeWorker(KillableWorker):
    @required_property
    def process(self):
        
    @required_property
    def is_active(self):
        return True

    def __str__(self):
        return "non-native worker %i" % self.pid


class WorkerStatus(KillableWorker):

    @required_property
    def status_fields(self):
        
    @lazy_property
    def acc(self):
        raw_value = self.status_fields.get('acc', '0/0/0')
        return tuple(coerce_value(int, n) for n in raw_value.split('/'))

    @lazy_property
    def child(self):
        return coerce_value(float, self.status_fields.get('child', '0'))

    @lazy_property
    def client(self):
        return self.status_fields.get('client')

    @lazy_property
    def conn(self):
        return coerce_value(float, self.status_fields.get('conn', '0'))

    @lazy_property
    def cpu(self):
        return coerce_value(float, self.status_fields.get('cpu', '0'))

    @property
    def is_idle(self):
        return self.m in IDLE_MODES

    @property
    def is_active(self):
        return not self.is_idle

    @lazy_property
    def m(self):
       return self.status_fields.get('m')

    @lazy_property
    def pid(self):
        return coerce_value(int, self.status_fields.get('pid'))

    @lazy_property
    def req(self):
        return coerce_value(int, self.status_fields.get('req'))

    @lazy_property
    def request(self):
        value = self.status_fields.get('request', 'NULL')
        return value if value != 'NULL' else None

    @lazy_property
    def slot(self):
        return coerce_value(float, self.status_fields.get('slot', '0'))

    @lazy_property
    def srv(self):
        raw_value = self.status_fields.get('srv', '0-0')
        return tuple(coerce_value(int, n) for n in raw_value.split('-'))

    @lazy_property
    def ss(self):
        return coerce_value(int, self.status_fields.get('ss', '0'))

    @lazy_property
    def vhost(self):
        return self.status_fields.get('vhost')

    def __str__(self):
        return "native worker %i (%s)" % (self.pid, "active" if self.is_active else "idle")


def parse_status_table(table):
    headings = dict((i, normalize_text(coerce_tag(th))) for i, th in enumerate(table.findAll('th')))
    logger.debug("Parsed table headings: %r", headings)
    for tr in table.findAll('tr'):
        values_by_index = [coerce_tag(td) for td in tr.findAll('td')]
        logger.debug("Parsed values by index: %r", values_by_index)
        if values_by_index:
            try:
                values_by_name = dict((headings[i], v) for i, v in enumerate(values_by_index))
                logger.debug("Parsed values by name: %r", values_by_name)
                yield values_by_name
            except Exception:
                pass


def coerce_tag(tag):
    try:
        return u''.join(tag.findAll(text=True)).strip()
    except Exception:
        return ''


def coerce_value(type, value):
    try:
        return type(value)
    except Exception:
        return None


def normalize_text(value):
    try:
        return re.sub('[^a-z0-9]', '', value.lower())
    except Exception:
        return ''
