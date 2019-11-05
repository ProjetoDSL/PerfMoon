# Author: Girardon <ggirardon@gmail.com>
# Last Change: Nov 05, 2019

import curses
import logging
import time

import coloredlogs


def watch_metrics(manager):
    try:
        curses.wrapper(redraw_loop, manager)
    except KeyboardInterrupt:
        pass


def redraw_loop(screen, manager):
    from perf_moon.cli import report_metrics, line_is_heading
    coloredlogs.set_level(logging.ERROR)
    cursor_mode = curses.curs_set(0)
    curses.noraw()
    screen.nodelay(True)
    try:
        while True:
            lnum = 0
            for line in report_metrics(manager):
                attributes = 0
                if line_is_heading(line):
                    attributes |= curses.A_BOLD
                screen.addstr(lnum, 0, line, attributes)
                lnum += 1
            screen.refresh()
            for i in range(10):
                if screen.getch() == ord('q'):
                    return
                time.sleep(0.1)
            manager.refresh()
            screen.erase()
    finally:
        curses.curs_set(cursor_mode)
        screen.erase()
