#!/usr/bin/env python

import sys
import json

from jsonselect import jsonselect

import gflags
FLAGS = gflags.FLAGS


def nodes_to_paths(nodes):
    '''Convert all nodes to paths.'''
    # TODO: de-dupe
    return [node_to_path(node) for node in nodes]


def node_to_path(node):
    '''Convert a jsonselect.Parser node to a path from root to that node.

    This returns an array of indices and strings, where there are either
    indexes into an array or keys in an object depending on whether they're
    strings or integers.

    Indices are 1-based!
    '''
    component = node.idx or node.parent_key
    rest = node_to_path(node.parent) if node.parent else []
    return rest + ([component] if component else [])


def apply_selector(selector, obj):
    nodes = get_result_nodes(selector, obj)
    paths = nodes_to_paths(nodes)


def select_path(path, in_obj, out_obj):
    '''Copy the portion of in_obj along path into out_obj.

    Note: we fill out an object rather than returning one to facilitate
    accumulating an output object from many paths.
    '''
    if len(path) == 0:
        raise ValueError("Can't select empty path.")

    component = path[0]
    if type(component) == int: component -= 1  # stupid 1-based CSS!
    if len(path) == 1:
        if type(component) == int:
            out_obj.append(in_obj[component])
        else:
            out_obj[component] = in_obj[component]
    else:
        selected = in_obj[component]
        try:
            new_out = out_obj[component]
            select_path(path[1:], selected, new_out)
        except (IndexError, KeyError):
            new_out = [] if isinstance(selected, list) else {}
            select_path(path[1:], selected, new_out)
            if type(component) == int:
                out_obj.append(new_out)
            else:
                out_obj[component] = new_out


def select_paths(paths, obj):
    '''Returns the union of all the paths selected on obj.'''
    base = [] if isinstance(obj, list) else {}
    for path in paths:
        select_path(path, obj, base)
    return base


def get_result_nodes(selector, obj):
    # This mirrors jsonselect.Parser.parse
    p = jsonselect.Parser(obj)
    tokens = jsonselect.lex(selector)

    if p.peek(tokens, 'operator') == '*':
        p.match(tokens, 'operator')
        results = list(jsonselect.object_iter(obj))
    else:
        results = p.selector_production(tokens)

    return results


UNSPECIFIED = 0
KEEP = 1
DELETE = 2

def filter_object(obj, marks, presumption=DELETE):
    '''Filter down obj based on marks, presuming keys should be kept/deleted.

    Args:
        obj: The object to be filtered. Filtering is done in-place.
        marks: An object mapping id(obj) --> {DELETE,KEEP}
               These values apply to the entire subtree, unless inverted.
        presumption: The default action to take on all keys.
    '''
    if isinstance(obj, list):
        keys = reversed(range(0, len(obj)))
    else:
        keys = obj.keys()

    for k in keys:
        v = obj[k]
        m = marks.get(id(v), UNSPECIFIED)
        if m == DELETE:
            del obj[k]  # an explicit deletion is irreversible.
        elif m == KEEP or presumption==KEEP:
            # keep descending, in case there are nodes we should delete.
            if isinstance(v, list) or isinstance(v, dict):
                filter_object(v, marks, presumption=KEEP)
        elif m == UNSPECIFIED:
            # ... and presumption == DELETE
            if isinstance(v, list) or isinstance(v, dict):
                filter_object(v, marks, presumption=DELETE)
                if len(v) == 0:
                    del obj[k]
            else:
                del obj[k]


if __name__ == '__main__':
    assert len(sys.argv) == 3
    _, selector, json_file = sys.argv

    obj = json.load(open(json_file))
    result = apply_selector(selector, obj)

    print json.dumps(result, indent=2)
