#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
# This file is part of Pynspect package (https://pypi.python.org/pypi/pynspect).
# Originally part of Mentat system (https://mentat.cesnet.cz/).
#
# Copyright (C) since 2016 CESNET, z.s.p.o (http://www.ces.net/).
# Copyright (C) since 2016 Jan Mach <honza.mach.ml@gmail.com>
# Use of this source is governed by the MIT license, see LICENSE file.
#-------------------------------------------------------------------------------


"""
This module provides tools for data filtering based on filtering and query
grammar.

The filtering grammar is thoroughly described in following module:

* :py:mod:`pynspect.lexer`

  Lexical analyzer, descriptions of valid grammar tokens.

* :py:mod:`pynspect.gparser`

  Grammar parser, language grammar description

* :py:mod:`pynspect.rules`

  Object representation of grammar rules, interface definition

* :py:mod:`pynspect.jpath`

  The addressing language JPath.

Please refer to appropriate module for more in-depth information.

There are two main tools in this package:

* :py:class:`DataObjectFilter`

  Tool capable of filtering data structures according to given filtering rules.

* :py:class:`IDEAFilterCompiler`

  Filter compiler, that ensures appropriate data types for correct variable
  comparison evaluation.

.. todo::

    There is quite a lot of code that needs to be written before actual filtering
    can take place. In the future, there should be some kind of object, that will
    be tailored for immediate processing and will take care of initializing
    uderlying parser, compiler and filter. This object will be designed later.

"""


__author__ = "Jan Mach <jan.mach@cesnet.cz>"
__credits__ = "Pavel Kácha <pavel.kacha@cesnet.cz>"


import re
import datetime


import ipranges
from pynspect.rules import IPV4Rule, IPV6Rule, DatetimeRule, IntegerRule, FloatRule, NumberRule, VariableRule,\
    LogicalBinOpRule, UnaryOperationRule, ComparisonBinOpRule, MathBinOpRule, ListRule
from pynspect.traversers import ListIP, FilteringTreeTraverser
from pynspect.jpath import jpath_values


TIMESTAMP_RE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]+))?([Zz]|(?:[+-][0-9]{2}:[0-9]{2}))$")


class DataObjectFilter(FilteringTreeTraverser):
    """
    Rule tree traverser implementing  default object filtering logic.

    Following example demonstrates DataObjectFilter usage in conjuction with
    PynspectFilterParser::

    >>> flt = DataObjectFilter()
    >>> psr = PynspectFilterParser()
    >>> psr.build()
    >>> rule = psr.parse('ID like "e214d2d9"')
    >>> result = flt.filter(rule, test_msg)

    Alternativelly rule tree can be created by hand/programatically:

    >>> rule = ComparisonBinOpRule('OP_GT', VariableRule("ConnCount"), IntegerRule(1))
    >>> result = flt.filter(rule, test_msg1)
    """
    def filter(self, rule, data):
        """
        Apply given filtering rule to given data structure.

        :param pynspect.rules.Rule rule: filtering rule to be checked
        :param any data: data structure to check against rule, ussually dict
        :return: True or False or expression result
        :rtype: bool or any
        """
        return rule.traverse(self, obj = data)

    #---------------------------------------------------------------------------

    def ipv4(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.ipv4` interface.
        """
        return rule.value

    def ipv6(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.ipv6` interface.
        """
        return rule.value

    def datetime(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.datetime` interface.
        """
        return rule.value

    def integer(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.integer` interface.
        """
        return rule.value

    def constant(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.constant` interface.
        """
        return rule.value

    def variable(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.variable` interface.
        """
        return jpath_values(kwargs['obj'], rule.value)

    def list(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.list` interface.
        """
        return rule.values()

    def binary_operation_logical(self, rule, left, right, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.binary_operation_logical` interface.
        """
        return self.evaluate_binop_logical(rule.operation, left, right, **kwargs)

    def binary_operation_comparison(self, rule, left, right, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.binary_operation_comparison` interface.
        """
        return self.evaluate_binop_comparison(rule.operation, left, right, **kwargs)

    def binary_operation_math(self, rule, left, right, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.binary_operation_math` interface.
        """
        return self.evaluate_binop_math(rule.operation, left, right, **kwargs)

    def unary_operation(self, rule, right, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.unary_operation` interface.
        """
        return self.evaluate_unop(rule.operation, right, **kwargs)


#-------------------------------------------------------------------------------


def compile_ip_v4(rule):
    """
    Compiler helper method: attempt to compile constant into object representing
    IPv4 address to enable relations and thus simple comparisons using Python
    operators.
    """
    if isinstance(rule.value, ipranges.Range):
        return rule
    return IPV4Rule(ipranges.from_str_v4(rule.value))

def compile_ip_v6(rule):
    """
    Compiler helper method: attempt to compile constant into object representing
    IPv6 address to enable relations and thus simple comparisons using Python
    operators.
    """
    if isinstance(rule.value, ipranges.Range):
        return rule
    return IPV6Rule(ipranges.from_str_v6(rule.value))

def compile_datetime(rule):
    """
    Compiler helper method: attempt to compile constant into object representing
    datetime object to enable relations and thus simple comparisons using Python
    operators.
    """
    if isinstance(rule.value, datetime.datetime):
        return rule
    try:
        # Try numeric type
        return DatetimeRule(datetime.datetime.fromtimestamp(float(rule.value)))
    except (TypeError, ValueError):
        pass
    # Try RFC3339 string
    res = TIMESTAMP_RE.match(str(rule.value))
    if res is not None:
        year, month, day, hour, minute, second = (int(n or 0) for n in res.group(*range(1, 7)))
        us_str = (res.group(7) or "0")[:6].ljust(6, "0")
        us = int(us_str)
        zonestr = res.group(8)
        zonespl = (0, 0) if zonestr in ['z', 'Z'] else [int(i) for i in zonestr.split(":")]
        zonediff = datetime.timedelta(minutes = zonespl[0]*60+zonespl[1])
        return DatetimeRule(datetime.datetime(year, month, day, hour, minute, second, us) - zonediff)
    else:
        raise ValueError("Wrong Timestamp")


CVRE = re.compile(r'\[\d+\]')
def clean_variable(var):
    """
    Remove any array indices from variable name to enable indexing into :py:data:`COMPILATIONS_IDEA_OBJECT`
    callback dictionary.

    This dictionary contains postprocessing callback appropriate for opposing
    operand of comparison operation for variable on given JPath.
    """
    return CVRE.sub('', var)


class IPListRule(ListRule):
    def __init__(self, rules):
        """
        Initialize the constant with given value.
        """
        self.value = rules

    def values(self):
        return ListIP([i.value for i in self.value])

    def __repr__(self):
        return "IPLIST({})".format(', '.join([repr(v) for v in self.value]))


COMPILATIONS_IDEA_OBJECT = {
    'CreateTime':   {'comp_i': compile_datetime, 'comp_l': ListRule },
    'DetectTime':   {'comp_i': compile_datetime, 'comp_l': ListRule },
    'EventTime':    {'comp_i': compile_datetime, 'comp_l': ListRule },
    'CeaseTime':    {'comp_i': compile_datetime, 'comp_l': ListRule },
    'WinStartTime': {'comp_i': compile_datetime, 'comp_l': ListRule },
    'WinEndTime':   {'comp_i': compile_datetime, 'comp_l': ListRule },
    'Source.IP4':   {'comp_i': compile_ip_v4,    'comp_l': IPListRule },
    'Target.IP4':   {'comp_i': compile_ip_v4,    'comp_l': IPListRule },
    'Source.IP6':   {'comp_i': compile_ip_v6,    'comp_l': IPListRule },
    'Target.IP6':   {'comp_i': compile_ip_v6,    'comp_l': IPListRule },
}


class IDEAFilterCompiler(FilteringTreeTraverser):
    """
    Rule tree traverser implementing IDEA filter compilation algorithm.

    Following example demonstrates DataObjectFilter usage in conjuction with
    PynspectFilterParser::

    >>> msg_idea = lite.Idea(test_msg)
    >>> flt = DataObjectFilter()
    >>> cpl = IDEAFilterCompiler()
    >>> psr = PynspectFilterParser()
    >>> psr.build()
    >>> rule = psr.parse('ID like "e214d2d9"')
    >>> rule = cpl.compile(rule)
    >>> result = flt.filter(rule, test_msg)
    """
    def compile(self, rule):
        """
        Compile given filtering rule into format appropriate for processing IDEA
        messages.

        :param pynspect.rules.Rule rule: filtering rule to be compiled
        :return: compiled filtering rule
        :rtype: pynspect.rules.Rule
        """
        return rule.traverse(self)


    #---------------------------------------------------------------------------


    def ipv4(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.ipv4` interface.
        """
        rule = compile_ip_v4(rule)
        return rule

    def ipv6(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.ipv6` interface.
        """
        rule = compile_ip_v4(rule)
        return rule

    def datetime(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.datetime` interface.
        """
        rule = compile_datetime(rule)
        return rule

    def integer(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.integer` interface.
        """
        rule.value = int(rule.value)
        return rule

    def constant(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.constant` interface.
        """
        return rule

    def variable(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.variable` interface.
        """
        return rule

    def list(self, rule, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.list` interface.
        """
        return rule

    def binary_operation_logical(self, rule, left, right, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.binary_operation_logical` interface.
        """
        return LogicalBinOpRule(rule.operation, left, right)

    def binary_operation_comparison(self, rule, left, right, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.binary_operation_comparison` interface.
        """
        var = val = None
        if isinstance(left, VariableRule) and not isinstance(right, VariableRule):
            var = left
            val = right
        elif isinstance(right, VariableRule) and not isinstance(left, VariableRule):
            var = right
            val = left
        if var and val:
            path = clean_variable(var.value)
            if path in COMPILATIONS_IDEA_OBJECT.keys():
                compilation = COMPILATIONS_IDEA_OBJECT[path]
                if isinstance(val, ListRule):
                    result = []
                    for itemv in val.value:
                        result.append(compilation['comp_i'](itemv))

                    right = compilation['comp_l'](result)
                else:
                    right = compilation['comp_i'](val)
        return ComparisonBinOpRule(rule.operation, left, right)

    def binary_operation_math(self, rule, left, right, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.binary_operation_math` interface.
        """
        if isinstance(left, IntegerRule) and isinstance(right, IntegerRule):
            result = self.evaluate_binop_math(rule.operation, left.value, right.value)
            if isinstance(result, list):
                return ListRule([IntegerRule(r) for r in result])
            return IntegerRule(result)
        elif isinstance(left, NumberRule) and isinstance(right, NumberRule):
            result = self.evaluate_binop_math(rule.operation, left.value, right.value)
            if isinstance(result, list):
                return ListRule([FloatRule(r) for r in result])
            return FloatRule(result)
        return MathBinOpRule(rule.operation, left, right)

    def unary_operation(self, rule, right, **kwargs):
        """
        Implementation of :py:func:`pynspect.traversers.RuleTreeTraverser.unary_operation` interface.
        """
        return UnaryOperationRule(rule.operation, right)


#-------------------------------------------------------------------------------


#
# Perform the demonstration.
#
if __name__ == "__main__":

    import pprint

    DEMO_DATA   = {"Test": 15, "Attr": "ABC"}
    DEMO_RULE   = ComparisonBinOpRule('OP_GT', VariableRule("Test"), IntegerRule(10))
    DEMO_FILTER = DataObjectFilter()
    pprint.pprint(DEMO_FILTER.filter(DEMO_RULE, DEMO_DATA))
