#!/usr/bin/env python

"""runner.py: Run multiple processes in parallel and get their output through a curses interface"""

import sys
import subprocess
import curses
import shlex
import time
import string
import Queue
from threading import Thread

__author__ = "Raido Pahtma"
__license__ = "MIT"


def read_process_output(process_output, queue):
    for line in iter(process_output.readline, b''):
        queue.put(line)
    process_output.close()


def read_stdin(input, queue):
    """
    Reading from stdin in a thread and then communicating through a queue.
    Could not get curses getch to perform reasonably and even this approach acts strangly sometimes(under load).
    Some threads don't seem to get equal attention or something ... really strange.
    """
    escape = False
    arrow = False
    while True:
        keys = input.read(1)
        for key in list(keys):
            if ord(key) == 0x0D:
                queue.put("ENTER")
            elif ord(key) == 0x7F:
                queue.put("BACKSPACE")
            elif escape:
                escape = False
                if ord(key) == 0x4F:
                    arrow = True
                else:
                    queue.put("escape %02X" % (ord(key)))
            elif arrow:
                arrow = False
                if key == "A":
                    queue.put("UP")
                elif key == "B":
                    queue.put("DOWN")
                elif key == "C":
                    queue.put("RIGHT")
                elif key == "D":
                    queue.put("LEFT")
                else:
                    queue.put("arrow %02X" % (ord(key)))
            elif ord(key) == 0x1B:
                escape = True
            elif key in string.printable:
                queue.put(key)
            else:
                queue.put("key %02X" % (ord(key)))


class Process():

    def __init__(self, name, cmd):
        self.name = name
        self.cmd = cmd
        self.text = ""
        self.p = None
        self.t = None
        self.q = Queue.Queue()
        self.error = False

    def start(self):
        try:
            self.p = subprocess.Popen(shlex.split(self.cmd), bufsize=0, close_fds=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.t = Thread(target=read_process_output, args=(self.p.stdout, self.q))
            self.t.daemon = True
            self.t.start()
        except Exception as e:
            self.text = "ERROR: %s" % (e)
            self.error = True

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

    inqueue = Queue.Queue()
    inthread = Thread(target=read_stdin, args=(sys.stdin, inqueue))
    inthread.daemon = True
    inthread.start()

    pointer = 0
    loop = 0
    enter = processcount
    terminate = processcount
    kill = processcount

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
                running_group = 0

                for p in processgroups[group]:
                    colorpair = 0

                    if p.update():
                        updates += 1

                    status = p.status()
                    if status == "*":
                        running_group += 1
                        running_total += 1
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
                        if status != "*" and status != 0:
                            p.start()
                            running_group += 1
                            running_total += 1
                    elif terminate == i:
                        if status == "*":
                            p.stop()
                    elif kill == i:
                        if status == "*":
                            p.kill()

                    try:
                        screen.addstr(3 + i, 4, "%s %s (%s): %s" % (group, p.name, status, p.text), curses.color_pair(colorpair))
                    except curses.error:
                        pass
                    i += 1

            try:
                screen.addstr(3 + i, 4, "---- ------ ---- (%s)" % (x))

                screen.addstr(3 + pointer, 2, "*")
                screen.addstr(3 + i + 1, 4, "(ENTER - start/retry, BACKSPACE - terminate, k - kill, a - toggle autostart, q - quit)")
                screen.addstr(3 + i + 2, 4, "")  # put the cursor here
            except curses.error:
                pass

            enter = processcount
            terminate = processcount
            kill = processcount

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
                        pointer = pointer - 1
                elif key == "DOWN":
                    pointer = (pointer + 1) % processcount
                elif key == "k":
                    kill = pointer
                elif key == "a":
                    autostart = not autostart
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
