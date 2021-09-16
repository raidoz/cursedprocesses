"""stinner.py: Read from stdin with curses and figure out what keys were pressed."""
import queue
import curses
import string
from threading import Thread

import sys

__author__ = "Raido Pahtma"
__license__ = "MIT"


def read_stdin(stdin_input, queue):
    """
    Reading from stdin in a thread and then communicating through a queue. Couldn't get curses getch to perform.
    """
    escape = False
    arrow = False
    page = False
    while True:
        keys = stdin_input.read(1)
        for key in list(keys):
            result = None
            if ord(key) == 0x0D:
                result = "ENTER"
            elif ord(key) == 0x7F:
                queue.put("BACKSPACE")
            elif escape:
                escape = False
                if ord(key) == 0x4F:
                    arrow = True
                elif ord(key) == 0x5B:
                    page = "page"
                else:
                    result = "escape %02X(%s)" % (ord(key), key)
            elif arrow:
                arrow = False
                if key == "A":
                    result = "UP"
                elif key == "B":
                    result = "DOWN"
                elif key == "C":
                    result = "RIGHT"
                elif key == "D":
                    result = "LEFT"
                elif key == "H":
                    result = "HOME"
                elif key == "F":
                    result = "END"
                else:
                    result = "arrow %02X(%s)" % (ord(key), key)
            elif page:
                if page == "page":
                    if key == "5":
                        page = "PAGE_UP"
                    elif key == "6":
                        page = "PAGE_DOWN"
                    elif key == "2":
                        page = "INSERT"
                    elif key == "3":
                        page = "DELETE"
                    else:
                        result = "page %02X(%s)" % (ord(key), key)
                else:
                    if key == "~":
                        result = page
                    else:
                        result = "page %s %02X(%s)" % (page, ord(key), key)
                    page = False
            elif ord(key) == 0x1B:
                escape = True
            elif key in string.printable:
                result = key
            else:
                result = "key %02X(%s)" % (ord(key), key)

            if result and queue.empty():
                queue.put(result)


if __name__ == '__main__':
    screen = curses.initscr()
    # curses.cbreak()
    # curses.noecho()
    screen.keypad(1)  # Get arrow keys to return ^[[A ^[[B ^[[C ^[[D

    inqueue = queue.Queue()
    inthread = Thread(target=read_stdin, args=(sys.stdin, inqueue))
    inthread.daemon = True
    inthread.start()

    while True:
        try:
            k = inqueue.get(False)
            print(k)
        except queue.Empty:
            pass
        except KeyboardInterrupt:
            break

    screen.keypad(0)
    curses.nocbreak()
    curses.echo()
    curses.endwin()
