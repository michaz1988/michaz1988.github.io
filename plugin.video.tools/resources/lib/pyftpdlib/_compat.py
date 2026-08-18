#!/usr/bin/env python

"""Small compatibility helpers used by the bundled FTP library."""

import os

def u(s):
    return s


def b(s):
    return s.encode("latin-1")


getcwdu = os.getcwd
unicode = str
xrange = range
long = int


# removed in 3.0, reintroduced in 3.2
try:
    callable = callable
except Exception:
    def callable(obj):
        for klass in type(obj).__mro__:
            if "__call__" in klass.__dict__:
                return True
        return False
