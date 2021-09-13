#!/usr/bin/env python

"""runner.py: Run multiple processes in parallel and get their output through a curses interface"""

import sys
import subprocess
import signal
import curses
import shlex
import time
import queue
from threading import Thread

from .stinner import read_stdin

__author__ = "Raido Pahtma"
__license__ = "MIT"


def read_process_output(process_output, queue):
    for line in iter(process_output.readline, b''):
        queue.put(line)
    process_output.close()


class Process():

    def __init__(self, name, cmd):
        self.name = name
        self.cmd = cmd
        self.text = ""
        self.p = None
        self.t = None
        self.q = queue.Queue()
        self.error = False

    def start(self):
        try:
            self.p = subprocess.Popen(shlex.split(self.cmd), bufsize=0, close_fds=True, stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.t = Thread(target=read_process_output, args=(self.p.stdout, self.q))
            self.t.daemon = True
            self.t.start()
        except Exception as e:
            self.text = "ERROR: %s" % (e)
            self.error = True

    def interrupt(self):
        self.p.send_signal(signal.SIGINT)

    def stop(self):
        self.p.terminate()

    def kill(self):
        self.p.kill()

    def update(self):
        try:
            line = self.q.get(False)  # (timeout=0.01)
            line = line.lstrip().rstrip()
            if len(line) > 0:
                self.text = line
                return True
        except Queue.Empty:
            return False

    def status(self):
        if self.error:
            return "E"
        if self.p is not None:
            s = self.p.poll()
            if s is None:
                return "*"
            return s
        return "#"

    def reset(self):
        if self.status() == "*":
            self.p.kill()
        self.text = ""
        self.p = None
        self.t = None
        self.q = queue.Queue()
        self.error = False


def mainloop(processgroups, parallel, total, autostart):
    screen = curses.initscr()
    # curses.cbreak()
    # curses.noecho()

    # sys.stdin = os.fdopen(sys.stdin.fileno(), 'r', 0)  # stdin needs to be totally unbuffered or arrow keys work badly
    screen.keypad(1)  # Get arrow keys to return ^[[A ^[[B ^[[C ^[[D

    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)

    processcount = 0
    for group in processgroups.values():
        processcount += len(group)

    inqueue = queue.Queue()
    inthread = Thread(target=read_stdin, args=(sys.stdin, inqueue))
    inthread.daemon = True
    inthread.start()

    pointer = 0
    loop = 0
    enter = processcount
    terminate = processcount
    kill = processcount
    interrupt = processcount

    x = "#"

    interrupted = False
    while not interrupted:
        try:
            screen.clear()
            screen.border(0)

            try:
                screen.addstr(2, 4, "---- %06u ---- (autostart=%s)" % (loop, autostart))
            except curses.error:
                pass

            i = 0
            updates = 0
            running_total = 0
            for group in sorted(processgroups):
                for p in processgroups[group]:
                    if p.status() == "*":
                        running_total += 1

            for group in sorted(processgroups):
                running_group = 0
                for p in processgroups[group]:
                    if p.status() == "*":
                        running_group += 1

                for p in processgroups[group]:
                    colorpair = 0

                    if p.update():
                        updates += 1

                    status = p.status()
                    if status == "*":
                        pass
                    elif status == "#":
                        if autostart:
                            if running_total < total:
                                if running_group < parallel:
                                    p.start()
                                    running_group += 1
                                    running_total += 1
                    elif status == 0:
                        colorpair = 2
                    else:
                        colorpair = 1

                    if enter == i:
                        if status != "*":
                            p.start()
                            running_group += 1
                            running_total += 1
                    elif terminate == i:
                        if status == "*":
                            p.stop()
                    elif kill == i:
                        if status == "*":
                            p.kill()
                    elif interrupt == i:
                        if status == "*":
                            p.interrupt()

                    try:
                        screen.addstr(3 + i, 4, "%s %s (%s): %s" % (group, p.name, status, p.text),
                                      curses.color_pair(colorpair))
                    except curses.error:
                        pass
                    i += 1

            try:
                screen.addstr(3 + i, 4, "---- ------ ---- (%s)" % (x))

                screen.addstr(3 + pointer, 2, "*")
                screen.addstr(3 + i + 1, 4, "(ENTER - start/retry, c - interrupt, t - terminate, k - kill, a - toggle autostart, r - reset failed, q - quit)")
                screen.addstr(3 + i + 2, 4, "")  # put the cursor here
            except curses.error:
                pass

            enter = processcount
            terminate = processcount
            kill = processcount
            interrupt = processcount

            screen.refresh()

            try:
                key = inqueue.get(False)
                if key == "ENTER":
                    enter = pointer
                elif key == "BACKSPACE":
                    terminate = pointer
                elif key == "UP":
                    if pointer == 0:
                        pointer = processcount - 1
                    else:
                        pointer -= 1
                elif key == "DOWN":
                    pointer = (pointer + 1) % processcount
                elif key == "HOME":
                    pointer = 0
                elif key == "END":
                    pointer = processcount - 1
                elif key == "PAGE_UP":
                    pointer -= 10
                    if pointer < 0:
                        pointer = 0
                elif key == "PAGE_DOWN":
                    pointer += 10
                    if pointer >= processcount:
                        pointer = processcount - 1
                elif key == "k":
                    kill = pointer
                elif key == "t":
                    terminate = pointer
                elif key == "c":
                    interrupt = pointer
                elif key == "a":
                    autostart = not autostart
                elif key == "r":
                    for group in processgroups.keys():
                        for p in processgroups[group]:
                            s = p.status()
                            if s != "*" and s != "#" and s != 0:
                                p.reset()
                elif key == "q":
                    interrupted = True
                x = key
            except Queue.Empty:
                pass

            loop += 1

            if updates == 0:
                time.sleep(0.1)

        except KeyboardInterrupt:
            interrupted = True

    screen.keypad(0)
    curses.nocbreak()
    curses.echo()
    curses.endwin()

    for group in sorted(processgroups):
        for p in processgroups[group]:
            status = p.status()
            if status == "*":
                print("Had to stop %s %s" % (group, p.name))
                p.stop()


def read_commands(commandfile):
    import csv
    groups = {}
    with open(commandfile, 'rb') as f:
        reader = csv.DictReader(f, fieldnames=("group", "name", "cmd"), delimiter=',')
        i = 0
        try:
            for row in reader:
                i += 1
                group = row["group"].lstrip().rstrip()
                if group.startswith("#") is False:
                    if group not in groups:
                        groups[group] = []

                    groups[group].append(Process(row["name"].lstrip().rstrip(), row["cmd"].lstrip().rstrip()))
        except AttributeError:
            raise AttributeError("Can't make sense of command row {:u}!".format(i))

    return groups


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Application arguments",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("input", help="Command file")
    parser.add_argument("--parallel", type=int, default=1, help="Number of parallel processes per group.")
    parser.add_argument("--total", type=int, default=12, help="Number of total parallel processes.")
    parser.add_argument("--manual", default=False, action="store_true", help="Processes must be started manually.")
    args = parser.parse_args()

    try:
        processes = read_commands(args.input)
        mainloop(processes, args.parallel, args.total, not args.manual)
    except AttributeError as e:
        print("ERROR: {}".format(e.message))


if __name__ == '__main__':
    main()
