import getopt
import json
import logging
import sys

import coloredlogs
from humanfriendly import (
    format_size,
    format_timespan,
    parse_size,
    parse_timespan,
    pluralize,
)
from humanfriendly.terminal import (
    ansi_wrap,
    connected_to_terminal,
    HIGHLIGHT_COLOR,
    usage,
)

from perf_moon import ApacheManager, NATIVE_WORKERS_LABEL
from perf_moon.interactive import watch_metrics

logger = logging.getLogger(__name__)


def main():
    coloredlogs.install(syslog=True)
    data_file = '/tmp/perf-moon.txt'
    dry_run = False
    max_memory_active = None
    max_memory_idle = None
    max_ss = None
    watch = False
    zabbix_discovery = False
    verbosity = 0

    try:
        options, arguments = getopt.getopt(sys.argv[1:], 'wa:i:t:f:znvqh', [
            'watch', 'max-memory-active=', 'max-memory-idle=', 'max-ss=',
            'max-time=', 'data-file=', 'zabbix-discovery', 'dry-run',
            'simulate', 'verbose', 'quiet', 'help',
        ])
        for option, value in options:
            if option in ('-w', '--watch'):
                watch = True
            elif option in ('-a', '--max-memory-active'):
                max_memory_active = parse_size(value)
            elif option in ('-i', '--max-memory-idle'):
                max_memory_idle = parse_size(value)
            elif option in ('-t', '--max-ss', '--max-time'):
                max_ss = parse_timespan(value)
            elif option in ('-f', '--data-file'):
                data_file = value
            elif option in ('-z', '--zabbix-discovery'):
                zabbix_discovery = True
            elif option in ('-n', '--dry-run', '--simulate'):
                logger.info("Performing a dry run ..")
                dry_run = True
            elif option in ('-v', '--verbose'):
                coloredlogs.increase_verbosity()
                verbosity += 1
            elif option in ('-q', '--quiet'):
                coloredlogs.decrease_verbosity()
                verbosity -= 1
            elif option in ('-h', '--help'):
                usage(__doc__)
                return
    except Exception as e:
        sys.stderr.write("Error: %s!\n" % e)
        sys.exit(1)
    # Execute the requested action(s).
    manager = ApacheManager()
    try:
        if max_memory_active or max_memory_idle or max_ss:
            manager.kill_workers(
                max_memory_active=max_memory_active,
                max_memory_idle=max_memory_idle,
                timeout=max_ss,
                dry_run=dry_run,
            )
        elif watch and connected_to_terminal(sys.stdout):
            watch_metrics(manager)
        elif zabbix_discovery:
            report_zabbix_discovery(manager)
        elif data_file != '-' and verbosity >= 0:
            for line in report_metrics(manager):
                if line_is_heading(line):
                    line = ansi_wrap(line, color=HIGHLIGHT_COLOR)
                print(line)
    finally:
        if (not watch) and (data_file == '-' or not dry_run):
            manager.save_metrics(data_file)


def report_metrics(manager):
    lines = ["Server metrics:"]
    for name, value in sorted(manager.server_metrics.items()):
        if name in ('total_traffic', 'bytes_per_second', 'bytes_per_request'):
            value = format_size(value)
        elif name == 'cpu_load':
            value = '%.1f%%' % value
        elif name == 'uptime':
            value = format_timespan(value)
        name = ' '.join(name.split('_'))
        name = name[0].upper() + name[1:]
        lines.append(" - %s: %s" % (name, value))
    main_label = "main Apache workers" if manager.wsgi_process_groups else "Apache workers"
    report_memory_usage(lines, main_label, manager.memory_usage)
    for name, memory_usage in sorted(manager.wsgi_process_groups.items()):
        report_memory_usage(lines, "WSGI process group '%s'" % name, memory_usage)
    return lines


def report_memory_usage(lines, label, memory_usage):
    lines.append("")
    workers = pluralize(len(memory_usage), "worker")
    lines.append("Memory usage of %s (%s):" % (label, workers))
    lines.append(" - Minimum: %s" % format_size(memory_usage.min))
    lines.append(" - Average: %s" % format_size(memory_usage.average))
    lines.append(" - Maximum: %s" % format_size(memory_usage.max))


def report_zabbix_discovery(manager):
    worker_groups = [NATIVE_WORKERS_LABEL] + sorted(manager.wsgi_process_groups.keys())
    print(json.dumps({'data': [{'{#NAME}': name} for name in worker_groups]}))


def line_is_heading(line):
    return line.endswith(':')
