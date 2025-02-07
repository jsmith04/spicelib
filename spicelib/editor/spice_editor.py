#!/usr/bin/env python
# coding=utf-8
# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        spice_editor.py
# Purpose:     Class made to update Generic Spice netlists
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import os
from pathlib import Path
import re
import logging

from .base_editor import BaseEditor, format_eng, ComponentNotFoundError, ParameterNotFoundError, PARAM_REGEX, \
    UNIQUE_SIMULATION_DOT_INSTRUCTIONS, Component, SUBCKT_DIVIDER

from typing import Union, List, Callable, Any, Tuple, Optional
from ..utils.detect_encoding import detect_encoding, EncodingDetectError

_logger = logging.getLogger("spicelib.SpiceEditor")

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2021, Fribourg Switzerland"

END_LINE_TERM = '\n'  #: This controls the end of line terminator used

# A Spice netlist can only have one of the instructions below, otherwise an error will be raised

REPLACE_REGXES = {
    'A': r"",  # LTSPice Only : Special Functions, Parameter substitution not supported
    'B': r"^(?P<designator>B§?[VI]?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>.*)$",  # Behavioral source
    'C': r"^(?P<designator>C§?\w+)(?P<nodes>(\s+\S+){2})(?P<model>\s+\w+)?\s+(?P<value>({)?(?(6).*}|([0-9\.E+-]+(Meg|[kmuµnpf])?F?))).*$",
    # Capacitor
    'D': r"^(?P<designator>D§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>\w+).*$",  # Diode
    'E': r"^(?P<designator>E§?\w+)(?P<nodes>(\s+\S+){2,4})\s+(?P<value>.*)$",  # Voltage Dependent Voltage Source
    # this only supports changing gain values
    'F': r"^(?P<designator>F§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>.*)$",  # Current Dependent Current Source
    # This implementation replaces everything after the 2 first nets
    'G': r"^(?P<designator>G§?\w+)(?P<nodes>(\s+\S+){2,4})\s+(?P<value>.*)$",  # Voltage Dependent Current Source
    # This only supports changing gain values
    'H': r"^(?P<designator>H§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>.*)$",  # Voltage Dependent Current Source
    # This implementation replaces everything after the 2 first nets
    'I': r"^(?P<designator>I§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>.*)$",  # Current Source
    # This implementation replaces everything after the 2 first nets
    'J': r"^(?P<designator>J§?\w+)(?P<nodes>(\s+\S+){3})\s+(?P<value>\w+).*$",  # JFET
    'K': r"^(?P<designator>K§?\w+)(?P<nodes>(\s+\S+){2,4})\s+(?P<value>[\+\-]?[0-9\.E+-]+[kmuµnpf]?).*$",
    # Mutual Inductance
    'L': r"^(?P<designator>L§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>({)?(?(5).*}|([0-9\.E+-]+(Meg|[kmuµnpf])?H?))).*$",
    # Inductance
    'M': r"^(?P<designator>M§?\w+)(?P<nodes>(\s+\S+){3,4})\s+(?P<value>\w+).*$",
    # MOSFET TODO: Parameters substitution not supported
    'O': r"^(?P<designator>O§?\w+)(?P<nodes>(\s+\S+){4})\s+(?P<value>\w+).*$",
    # Lossy Transmission Line TODO: Parameters substitution not supported
    'Q': r"^(?P<designator>Q§?\w+)(?P<nodes>(\s+\S+){3,4})\s+(?P<value>\w+).*$",
    # Bipolar TODO: Parameters substitution not supported
    'R': r"^(?P<designator>R§?\w+)(?P<nodes>(\s+\S+){2})(?P<model>\s+\w+)?\s+(?P<value>(R=)?({)?(?(7).*}|([0-9\.E+-]+(Meg|[kmuµnpf])?R?)\d*)).*$",
    # Resistors
    'S': r"^(?P<designator>S§?\w+)(?P<nodes>(\s+\S+){4})\s+(?P<value>.*)$",  # Voltage Controlled Switch
    'T': r"^(?P<designator>T§?\w+)(?P<nodes>(\s+\S+){4})\s+(?P<value>.*)$",  # Lossless Transmission
    'U': r"^(?P<designator>U§?\w+)(?P<nodes>(\s+\S+){3})\s+(?P<value>.*)$",  # Uniform RC-line
    'V': r"^(?P<designator>V§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>.*)$",  # Voltage Source
    # This implementation replaces everything after the 2 first nets
    'W': r"^(?P<designator>W§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>.*)$",  # Current Controlled Switch
    # This implementation replaces everything after the 2 first nets
    'X': r"^(?P<designator>X§?\w+)(?P<nodes>(\s+\S+){1,99}?)\s+(?P<value>\w+)(\s+params:)?(?P<params>(\s+\w+\s*=\s*[\d\w\{\}\(\)\-\+\*/]+)*)\s*\\?$",
    # Sub-circuit, Parameter substitution not supported
    'Z': r"^(?P<designator>Z§?\w+)(?P<nodes>(\s+\S+){3})\s+(?P<value>\w+).*$",
    # MESFET and IBGT. TODO: Parameters substitution not supported
    '@': r"^(?P<designator>@§?\d+)(?P<nodes>(\s+\S+){2})\s?(?P<params>(.*)*)$",
    # Frequency Noise Analysis (FRA) wiggler
    # pattern = r'^@(\d+)\s+(\w+)\s+(\w+)(?:\s+delay=(\d+\w+))?(?:\s+fstart=(\d+\w+))?(?:\s+fend=(\d+\w+))?(?:\s+oct=(\d+))?(?:\s+fcoarse=(\d+\w+))?(?:\s+nmax=(\d+\w+))?\s+(\d+)\s+(\d+\w+)\s+(\d+)(?:\s+pp0=(\d+\.\d+))?(?:\s+pp1=(\d+\.\d+))?(?:\s+f0=(\d+\w+))?(?:\s+f1=(\d+\w+))?(?:\s+tavgmin=(\d+\w+))?(?:\s+tsettle=(\d+\w+))?(?:\s+acmag=(\d+))?$'
    'Ã': r"^(?P<designator>Ã\w+)(?P<nodes>(\s+\S+){16})\s+(?P<value>.*)(?P<params>(\s+\w+\s*=\s*[\d\w\{\}\(\)\-\+\*/]+)*)\s*\\?$",  # QSPICE Unique component Ã
    '¥': r"^(?P<designator>¥\w+)(?P<nodes>(\s+\S+){16})\s+(?P<value>.*)(?P<params>(\s+\w+\s*=\s*[\d\w\{\}\(\)\-\+\*/]+)*)\s*\\?$",  # QSPICE Unique component ¥
    '€': r"^(?P<designator>€\w+)(?P<nodes>(\s+\S+){32})\s+(?P<value>.*)(?P<params>(\s+\w+\s*=\s*[\d\w\{\}\(\)\-\+\*/]+)*)\s*\\?$",  # QSPICE Unique component €
    '£': r"^(?P<designator>£\w+)(?P<nodes>(\s+\S+){64})\s+(?P<value>.*)(?P<params>(\s+\w+\s*=\s*[\d\w\{\}\(\)\-\+\*/]+)*)\s*\\?$",  # QSPICE Unique component £
    'Ø': r"^(?P<designator>Ø\w+)(?P<nodes>(\s+\S+){1,99})\s+(?P<value>.*)(?P<params>(\s+\w+\s*=\s*[\d\w\{\}\(\)\-\+\*/]+)*)\s*\\?$",  # QSPICE Unique component Ø
    '×': r"^(?P<designator>×\w+)(?P<nodes>(\s+\S+){4,16})\s+(?P<value>.*)(?P<params>(\w+\s+){1,8})\s*\\?$",  # QSPICE proprietaty component ×
    'Ö': r"^(?P<designator>Ö\w+)(?P<nodes>(\s+\S+){5})\s+(?P<params>.*)\s*\\?$",  # LTspice proprietary component Ö
}

SUBCKT_CLAUSE_FIND = r"^.SUBCKT\s+"

# Code Optimization objects, avoiding repeated compilation of regular expressions
component_replace_regexs = {prefix: re.compile(pattern, re.IGNORECASE) for prefix, pattern in REPLACE_REGXES.items()}
subckt_regex = re.compile(r"^.SUBCKT\s+(?P<name>\w+)", re.IGNORECASE)
lib_inc_regex = re.compile(r"^\.(LIB|INC)\s+(.*)$", re.IGNORECASE)

LibSearchPaths = []


def get_line_command(line) -> str:
    """
    Retrives the type of SPICE command in the line.
    Starts by removing the leading spaces and the evaluates if it is a comment, a directive or a component.
    """
    if isinstance(line, str):
        for i in range(len(line)):
            ch = line[i]
            if ch == ' ' or ch == '\t':
                continue
            else:
                ch = ch.upper()
                if ch in REPLACE_REGXES:  # A circuit element
                    return ch
                elif ch == '+':
                    return '+'  # This is a line continuation.
                elif ch in "#;*\n\r":  # It is a comment or a blank line
                    return "*"
                elif ch == '.':  # this is a directive
                    j = i + 1
                    while j < len(line) and (line[j] not in (' ', '\t', '\r', '\n')):
                        j += 1
                    return line[i:j].upper()
                else:
                    raise SyntaxError('Unrecognized command in line "%s" of file %s' % line)
    elif isinstance(line, SpiceCircuit):
        return ".SUBCKT"
    else:
        raise SyntaxError('Unrecognized command in line "{}"'.format(line))


def _first_token_upped(line):
    """
    (Private function. Not to be used directly)
    Returns the first non-space character in the line. If a point '.' is found, then it gets the primitive associated.
    """
    i = 0
    while i < len(line) and line[i] in (' ', '\t'):
        i += 1
    j = i
    while i < len(line) and not (line[i] in (' ', '\t')):
        i += 1
    return line[j:i].upper()


def _is_unique_instruction(instruction):
    """
    (Private function. Not to be used directly)
    Returns true if the instruction is one of the unique instructions
    """
    cmd = get_line_command(instruction)
    return cmd in UNIQUE_SIMULATION_DOT_INSTRUCTIONS


class UnrecognizedSyntaxError(Exception):
    """Line doesn't match expected Spice syntax"""

    def __init__(self, line, regex):
        super().__init__(f'Line: "{line}" doesn\'t match regular expression "{regex}"')


class MissingExpectedClauseError(Exception):
    """Missing expected clause in Spice netlist"""


class SpiceCircuit(BaseEditor):
    """
    Represents sub-circuits within a SPICE circuit. Since sub-circuits can have sub-circuits inside
    them, it serves as base for the top level netlist. This hierarchical approach helps to encapsulate
    and protect parameters and components from edits made at a higher level.
    """

    def __init__(self):
        super().__init__()
        self.netlist = []

    def _get_line_starting_with(self, substr: str) -> int:
        """Internal function. Do not use."""
        # This function returns the line number that starts with the substr string.
        # If the line is not found, then -1 is returned.
        substr_upper = substr.upper()
        for line_no, line in enumerate(self.netlist):
            if isinstance(line, SpiceCircuit):  # If it is a sub-circuit it will simply ignore it.
                continue
            line_upcase = _first_token_upped(line)
            if line_upcase == substr_upper:
                return line_no
        error_msg = "line starting with '%s' not found in netlist" % substr
        _logger.error(error_msg)
        raise ComponentNotFoundError(error_msg)

    def _add_lines(self, line_iter):
        """Internal function. Do not use.
        Add a list of lines to the netlist."""
        for line in line_iter:
            cmd = get_line_command(line)
            if cmd == '.SUBCKT':
                sub_circuit = SpiceCircuit()
                sub_circuit.netlist.append(line)
                # Advance to the next non nested .ENDS
                finished = sub_circuit._add_lines(line_iter)
                if finished:
                    self.netlist.append(sub_circuit)
                else:
                    return False
            elif cmd == '+':
                assert len(self.netlist) > 0, "ERROR: The first line cannot be starting with a +"
                self.netlist[-1] += line  # Appends to the last line
            else:
                self.netlist.append(line)
                if cmd[:4] == '.END':  # True for either .END and .ENDS primitives
                    return True  # If a sub-circuit is ended correctly, returns True
        return False  # If a sub-circuit ends abruptly, returns False

    def write_lines(self, f):
        """Internal function. Do not use."""
        # This helper function writes the contents of sub-circuit to the file f
        for command in self.netlist:
            if isinstance(command, SpiceCircuit):
                command.write_lines(f)
            else:
                f.write(command)

    def _get_line_matching(self, command, search_expression: re.Pattern) -> Tuple[int, Union[re.Match, None]]:
        """
        Internal function. Do not use. Returns a line starting with command and matching the search with the regular
        expression
        """
        line_no = 0
        while line_no < len(self.netlist):
            line = self.netlist[line_no]
            if isinstance(line, SpiceCircuit):  # If it is a sub-circuit it will simply ignore it.
                line_no += 1
                continue
            cmd = get_line_command(line)
            if cmd == command:
                match = search_expression.search(line)
                if match:
                    return line_no, match
            line_no += 1
        return -1, None  # If it fails, it returns an invalid line number and No match

    def get_subcircuit(self, instance_name: str) -> 'SpiceCircuit':
        """
        Returns an object representing a Subcircuit. This object can manipulate elements such as the SpiceEditor does.
        :param instance_name: Reference of the subcircuit
        :type instance_name: str
        :returns: SpiceCircuit instance
        :rtype: SpiceCircuit
        :raises UnrecognizedSyntaxError: when an spice command is not recognized by spicelib
        :raises ComponentNotFoundError: When the reference was not found
        """
        global LibSearchPaths
        if SUBCKT_DIVIDER in instance_name:
            subckt_ref, sub_subckts = instance_name.split(SUBCKT_DIVIDER, 1)
        else:
            subckt_ref = instance_name

        line_no = self._get_line_starting_with(subckt_ref)
        sub_circuit_instance = self.netlist[line_no]
        regex = component_replace_regexs['X']  # The sub-circuit instance regex
        m = regex.search(sub_circuit_instance)
        if m:
            subcircuit_name = m.group('value')  # last_token of the line before Params:
        else:
            raise UnrecognizedSyntaxError(sub_circuit_instance, REPLACE_REGXES['X'])

        # Search for the sub-circuit in the netlist
        sub_circuit = SpiceEditor.find_subckt_in_lib(self.circuit_file, subcircuit_name)

        if sub_circuit is None:  # If it was not found in the netlist, search on the declared libraries
            # If we reached here is because the subcircuit was not found. Search for it in declared libraries
            for line in self.netlist:
                m = lib_inc_regex.match(line)
                if m:  # If it is a library include
                    lib = m.group(2)
                    if os.path.exists(lib):
                        lib_filename = os.path.join(os.path.expanduser('~'), "Documents\\LTspiceXVII\\lib\\sub", lib)
                        if os.path.exists(lib_filename):
                            sub_circuit = SpiceEditor.find_subckt_in_lib(lib_filename, subcircuit_name)
                            if sub_circuit:
                                break
                    for path in LibSearchPaths:
                        lib_filename = os.path.join(path, lib)
                        if os.path.exists(lib_filename):
                            sub_circuit = SpiceEditor.find_subckt_in_lib(lib_filename, subcircuit_name)
                            if sub_circuit:
                                break

        if sub_circuit:
            if SUBCKT_DIVIDER in instance_name:
                return sub_circuit.get_subcircuit(sub_subckts)
            else:
                return sub_circuit
        else:
            # The search was not successful
            raise ComponentNotFoundError(f'Sub-circuit "{subcircuit_name}" not found')

    def _set_model_and_value(self, component, value):
        """Internal function. Do not use."""
        prefix = component[0]  # Using the first letter of the component to identify what is it
        regex = component_replace_regexs.get(prefix, None)  # Obtain RegX to make the update

        if regex is None:
            error_msg = f"Component must start with one of these letters: {','.join(REPLACE_REGXES.keys())}\n" \
                        f"Got {component}"
            _logger.error(error_msg)
            return

        if isinstance(value, (int, float)):
            value = format_eng(value)

        line_no = self._get_line_starting_with(component)

        line = self.netlist[line_no]
        m = regex.match(line)
        if m is None:
            raise UnrecognizedSyntaxError(line, REPLACE_REGXES[prefix])
        else:
            start = m.start('value')
            end = m.end('value')
            self.netlist[line_no] = line[:start] + value + line[end:]

    def reset_netlist(self, create_blank: bool = False) -> None:
        """
        Reverts all changes done to the netlist. If create_blank is set to True, then the netlist is blanked.

        :param create_blank: If True, the netlist is blanked. That is, all primitives and components are erased.
        :type create_blank: bool
        :returns: None
        """
        self.netlist.clear()

    def clone(self, **kwargs) -> 'SpiceCircuit':
        """
        Creates a new copy of the SpiceCircuit. Changes done at the new copy do not affect the original.

        :key new_name: The new name to be given to the circuit
        :key type new_name: str
        :return: The new replica of the SpiceCircuit object
        :rtype: SpiceCircuit
        """
        clone = SpiceCircuit()
        clone.netlist = self.netlist.copy()
        clone.netlist.insert(0, "***** SpiceEditor Manipulated this sub-circuit ****" + END_LINE_TERM)
        clone.netlist.append("***** ENDS SpiceEditor ****" + END_LINE_TERM)
        new_name = kwargs.get('new_name', None)
        if new_name:  # If it is different from None
            clone.setname(new_name)
        return clone

    def name(self) -> str:
        """
        Returns the name of the Sub-Circuit.

        :rtype: str
        """
        if len(self.netlist):
            for line in self.netlist:
                m = subckt_regex.search(line)
                if m:
                    return m.group('name')
            else:
                raise RuntimeError("Unable to find .SUBCKT clause in subcircuit")
        else:
            raise RuntimeError("Empty Subcircuit")

    def setname(self, new_name: str):
        """
        Renames the sub-circuit to a new name. No check is done to the new name.
        It is up to the user to make sure that the new name is valid.

        :param new_name: The new Name.
        :type new_name: str
        :return: Nothing
        :rtype: None
        """
        if len(self.netlist):
            lines = len(self.netlist)
            line_no = 0
            while line_no < lines:
                line = self.netlist[line_no]
                m = subckt_regex.search(line)
                if m:
                    # Replacing the name in the SUBCKT Clause
                    start = m.start('name')
                    end = m.end('name')
                    self.netlist[line_no] = line[:start] + new_name + line[end:]
                    break
                line_no += 1
            else:
                raise MissingExpectedClauseError("Unable to find .SUBCKT clause in subcircuit")

            # This second loop finds the .ENDS clause
            while line_no < lines:
                line = self.netlist[line_no]
                if get_line_command(line) == '.ENDS':
                    self.netlist[line_no] = '.ENDS ' + new_name + END_LINE_TERM
                    break
                line_no += 1
            else:
                raise MissingExpectedClauseError("Unable to find .SUBCKT clause in subcircuit")
        else:
            # Avoiding exception by creating an empty sub-circuit
            self.netlist.append("* SpiceEditor Created this sub-circuit")
            self.netlist.append('.SUBCKT %s%s' % (new_name, END_LINE_TERM))
            self.netlist.append('.ENDS %s%s' % (new_name, END_LINE_TERM))

    def get_component_info(self, reference) -> dict:
        """
        Retrieves the component information as defined in the corresponding REGEX. The line number is also added.

        :param reference: Reference of the component
        :type reference: str
        :return: Dictionary with the component information
        :rtype: dict
        :raises: ComponentNotFoundError - In case the component is not found
        :raises: UnrecognizedSyntaxError when the line doesn't match the expected REGEX.
        :raises: NotImplementedError if there isn't an associated regular expression for the component prefix.
        """
        if SUBCKT_DIVIDER in reference:
            raise NotImplementedError("This method doesn't support hierarchical access. "
                                      "Please use set_component_value() and get_component_value() methods.")
        prefix = reference[0]  # Using the first letter of the component to identify what is it
        regex = component_replace_regexs.get(prefix, None)  # Obtain RegX to make the update

        if regex is None:
            error_msg = f"Component must start with one of these letters: {','.join(REPLACE_REGXES.keys())}\n" \
                        f"Got {reference}"
            _logger.warning(error_msg)
            raise NotImplementedError("Unsuported prefix {}".format(prefix))

        line_no = self._get_line_starting_with(reference)
        line = self.netlist[line_no]
        m = regex.match(line)
        if m is None:
            error_msg = 'Unsupported line "{}"\nExpected format is "{}"'.format(line, REPLACE_REGXES[prefix])
            _logger.error(error_msg)
            raise UnrecognizedSyntaxError(line, REPLACE_REGXES[prefix])

        info = m.groupdict()
        info['line'] = line_no  # adding the line number to the component information
        return info

    def get_component(self, reference: str) -> Union[Component, 'SpiceCircuit']:
        """
        Returns an object representing the given reference in the schematic file.

        :param reference: Reference of the component
        :type reference: str
        :return: The Component object or a SpiceSubcircuit in case of hierarchical design
        :rtype: Component or SpiceSubcircuit
        :raises: ComponentNotFoundError - In case the component is not found
        :raises: UnrecognizedSyntaxError when the line doesn't match the expected REGEX.
        :raises: NotImplementedError if there isn't an associated regular expression for the component prefix.
        """
        component_info = self.get_component_info(reference)
        component = Component()
        component.reference = reference
        component.ports = component_info['nodes'].split()
        for attr in component_info:
            if attr not in ('designator', 'nodes'):
                component.attributes[attr] = component_info[attr]
        return component

    def get_component_attribute(self, reference: str, attribute: str) -> Optional[str]:
        """
        Returns the attribute of a component retrieved from the netlist.

        :param reference: Reference of the component
        :type reference: str
        :param attribute: Name of the attribute to be retrieved
        :type attribute: str
        :return: Value of the attribute
        :rtype: str
        :raises: ComponentNotFoundError - In case the component is not found
        :raises: UnrecognizedSyntaxError when the line doesn't match the expected REGEX.
        :raises: NotImplementedError if there isn't an associated regular expression for the component prefix.
        """
        component_info = self.get_component_info(reference)
        return component_info.get(attribute, None)

    def get_parameter(self, param: str) -> str:
        """
        Returns the value of a parameter retrieved from the netlist.

        :param param: Name of the parameter to be retrieved
        :type param: str
        :return: Value of the parameter being sought
        :rtype: str
        :raises: ParameterNotFoundError - In case the component is not found
        """
        regx = re.compile(PARAM_REGEX % param, re.IGNORECASE)
        line_no, match = self._get_line_matching('.PARAM', regx)
        if match:
            return match.group('value')
        else:
            raise ParameterNotFoundError(param)

    def set_parameter(self, param: str, value: Union[str, int, float]) -> None:
        """Sets the value of a parameter in the netlist. If the parameter is not found, it is added to the netlist.

        Usage: ::

         LTC.set_parameter("TEMP", 80)

        This adds onto the netlist the following line: ::

         .PARAM TEMP=80

        This is an alternative to the set_parameters which is more pythonic in its usage
        and allows setting more than one parameter at once.

        :param param: Spice Parameter name to be added or updated.
        :type param: str

        :param value: Parameter Value to be set.
        :type value: str, int or float

        :return: Nothing
        """
        regx = re.compile(PARAM_REGEX % param, re.IGNORECASE)
        param_line, match = self._get_line_matching('.PARAM', regx)
        if match:
            start, stop = match.span(regx.groupindex['replace'])
            line: str = self.netlist[param_line]
            self.netlist[param_line] = line[:start] + "{}={}".format(param, value) + line[stop:]
        else:
            # Was not found
            # the last two lines are typically (.backano and .end)
            insert_line = len(self.netlist) - 2
            self.netlist.insert(insert_line, '.PARAM {}={}  ; Batch instruction'.format(param, value) + END_LINE_TERM)

    def set_component_value(self, device: str, value: Union[str, int, float]) -> None:
        """
        Changes the value of a component, such as a Resistor, Capacitor or Inductor.
        For components inside sub-circuits, use the sub-circuit designator prefix with ':' as separator (Example X1:R1)
        Usage: ::

            LTC.set_component_value('R1', '3.3k')
            LTC.set_component_value('X1:C1', '10u')

        :param device: Reference of the circuit element to be updated.
        :type device: str
        :param value:
            value to be set on the given circuit element. Float and integer values will be automatically
            formatted as per the engineering notations 'k' for kilo, 'm', for mili and so on.
        :type value: str, int or float
        :raises:
            ComponentNotFoundError - In case the component is not found

            ValueError - In case the value doesn't correspond to the expected format

            NotImplementedError - In case the circuit element is defined in a format which is not supported by this
            version.

            If this is the case, use GitHub to start a ticket.  https://github.com/nunobrum/spicelib
        """
        self._set_model_and_value(device, value)

    def set_element_model(self, element: str, model: str) -> None:
        """Changes the value of a circuit element, such as a diode model or a voltage supply.
        Usage: ::

            LTC.set_element_model('D1', '1N4148')
            LTC.set_element_model('V1' "SINE(0 1 3k 0 0 0)")

        :param element: Reference of the circuit element to be updated.
        :type element: str
        :param model: model name of the device to be updated
        :type model: str

        :raises:
            ComponentNotFoundError - In case the component is not found

            ValueError - In case the model format contains irregular characters

            NotImplementedError - In case the circuit element is defined in a format which is not supported by this version.

            If this is the case, use GitHub to start a ticket.  https://github.com/nunobrum/spicelib
        """
        self._set_model_and_value(element, model)

    def get_component_value(self, element: str) -> str:
        """
        Returns the value of a component retrieved from the netlist.

        :param element: Reference of the circuit element to get the value.
        :type element: str

        :return: value of the circuit element .
        :rtype: str

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        return self.get_component_info(element)['value']

    def get_component_nodes(self, element: str) -> List[str]:
        """
        Returns the nodes to which the component is attached to.

        :param element: Reference of the circuit element to get the nodes.
        :type element: str
        :return: List of nodes
        :rtype: list
        """
        nodes = self.get_component_info(element)['nodes']
        nodes = nodes.split()  # Remove any spaces if they exist. This considers \r \n \t characters as well
        return nodes

    def get_components(self, prefixes='*') -> list:
        """
        Returns a list of components that match the list of prefixes indicated on the parameter prefixes.
        In case prefixes is left empty, it returns all the ones that are defined by the REPLACE_REGEXES.
        The list will contain the designators of all components found.

        :param prefixes:
            Type of prefixes to search for. Examples: 'C' for capacitors; 'R' for Resistors; etc... See prefixes
            in SPICE documentation for more details.
            The default prefix is '*' which is a special case that returns all components.
        :type prefixes: str

        :return:
            A list of components matching the prefixes demanded.
        """
        answer = []
        if prefixes == '*':
            prefixes = ''.join(REPLACE_REGXES.keys())
        for line in self.netlist:
            if isinstance(line, SpiceCircuit):  # Only gets components from the main netlist,
                # it currently skips sub-circuits
                continue
            tokens = line.split()
            try:
                if tokens[0][0] in prefixes:
                    answer.append(tokens[0])  # Appends only the designators
            except IndexError or TypeError:
                pass
        return answer

    def add_component(self, component: Component, **kwargs) -> None:
        """
        Adds a component to the netlist. The component is added to the end of the netlist,
        just before the .END statement. If the component already exists, it will be replaced by the new one.

        :param component: The component to be added to the netlist
        :type component: Component
        :param kwargs:
            The following keyword arguments are supported:

            * **insert_before** (str) - The reference of the component before which the new component should be inserted.
            * **insert_after** (str) - The reference of the component after which the new component should be inserted.
        :return: Nothing
        """
        if 'insert_before' in kwargs:
            line_no = self._get_line_starting_with(kwargs['insert_before'])
        elif 'insert_after' in kwargs:
            line_no = self._get_line_starting_with(kwargs['insert_after'])
        else:
            # Insert before backanno instruction
            try:
                line_no = self.netlist.index(
                    '.backanno\n')  # TODO: Improve this. END of line termination could be differnt
            except ValueError:
                line_no = len(self.netlist) - 2

        nodes = " ".join(component.ports)
        model = component.attributes.get('model', 'no_model')
        parameters = " ".join([f"{k}={v}" for k, v in component.attributes.items() if k != 'model'])
        component_line = f"{component.reference} {nodes} {model} {parameters}{END_LINE_TERM}"
        self.netlist.insert(line_no, component_line)

    def remove_component(self, designator: str) -> None:
        """
        Removes a component from  the design. Current implementation only allows removal of a component
        from the main netlist, not from a sub-circuit.

        :param designator: Component reference in the design. Ex: V1, C1, R1, etc...
        :type designator: str

        :return: Nothing
        :raises: ComponentNotFoundError - When the component doesn't exist on the netlist.
        """
        line = self._get_line_starting_with(designator)
        self.netlist[line] = ''  # Blanks the line

    @staticmethod
    def add_library_search_paths(paths: Union[str, List[str]]) -> None:
        """
        Adds search paths for libraries. By default, the local directory and the
        ~username/"Documents/LTspiceXVII/lib/sub will be searched forehand. Only when a library is not found in these
        paths then the paths added by this method will be searched.
        Alternatively spicelib.SpiceEditor.LibSearchPaths.append(paths) can be used."

        :param paths: Path to add to the Search path
        :type paths: str
        :return: Nothing
        :rtype: None
        """
        global LibSearchPaths
        if isinstance(paths, str):
            LibSearchPaths.append(paths)
        elif isinstance(paths, list):
            LibSearchPaths += paths

    def get_all_nodes(self) -> List[str]:
        """
        Retrieves all nodes existing on a Netlist.

        :returns: Circuit Nodes
        :rtype: list[str]
        """
        circuit_nodes = []
        for line in self.netlist:
            prefix = get_line_command(line)
            if prefix in component_replace_regexs:
                match = component_replace_regexs[prefix].match(line)
                if match:
                    nodes = match.group('nodes').split()  # This separates by all space characters including \t
                    for node in nodes:
                        if node not in circuit_nodes:
                            circuit_nodes.append(node)
        return circuit_nodes

    def save_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        # docstring is in the parent class
        pass

    def add_instruction(self, instruction: str) -> None:
        # docstring is in the parent class
        pass

    def remove_instruction(self, instruction: str) -> None:
        # docstring is in the parent class
        pass

    def remove_Xinstruction(self, search_pattern: str) -> None:
        # docstring is in the parent class
        pass

    @property
    def circuit_file(self) -> Path:
        """
        Returns the path of the circuit file. Always returns an empty Path for SpiceCircuit.
        """
        return Path('')


class SpiceEditor(SpiceCircuit):
    """
    Provides interfaces to manipulate SPICE netlist files. The class doesn't update the netlist file
    itself. After implementing the modifications the user should call the "save_netlist" method to write a new
    netlist file.

    :param netlist_file: Name of the .NET file to parse
    :type netlist_file: str or Path
    :param encoding: Forcing the encoding to be used on the circuit netlile read. Defaults to 'autodetect' which will
        call a function that tries to detect the encoding automatically. This however is not 100% foolproof.
    :param create_blank: Create a blank '.net' file when 'netlist_file' not exist.
    :type encoding: str, optional
    """

    def __init__(self, netlist_file: Union[str, Path], encoding='autodetect', create_blank=False):
        super().__init__()
        self.netlist_file = Path(netlist_file)
        self.modified_subcircuits = {}
        if create_blank:
            self.encoding = 'utf-8'  # when user want to create a blank netlist file, and didn't set encoding.
        else:
            if encoding == 'autodetect':
                try:
                    self.encoding = detect_encoding(self.netlist_file, r'^\* ')  # Normally the file will start with a '*'
                except EncodingDetectError as err:
                    raise err
            else:
                self.encoding = encoding
        self.reset_netlist(create_blank)

    @property
    def circuit_file(self) -> Path:
        return self.netlist_file

    def get_component_info(self, component) -> dict:
        prefix = component[0]
        if prefix == 'X' and SUBCKT_DIVIDER in component:  # Replaces a component inside of a subciruit
            # In this case the sub-circuit needs to be copied so that is copy is modified. A copy is created for each
            # instance of a sub-circuit.
            component_split = component.split(SUBCKT_DIVIDER)
            modified_path = SUBCKT_DIVIDER.join(component_split[:-1])  # excludes last component
            component = component_split[-1]  # This is the last component to modify

            if modified_path in self.modified_subcircuits:  # See if this was already a modified sub-circuit instance
                subcircuit = self.modified_subcircuits[modified_path]
            else:
                subcircuit = self.get_subcircuit(component)
            return subcircuit.get_component_info(component)

        return super().get_component_info(component)

    def _set_model_and_value(self, component, value):
        """
        Internal method to set the model and value of a component.
        """
        prefix = component[0]  # Using the first letter of the component to identify what is it
        if prefix == 'X' and SUBCKT_DIVIDER in component:  # Relaces a component inside of a subciruit
            # In this case the sub-circuit needs to be copied so that is copy is modified. A copy is created for each
            # instance of a sub-circuit.
            component_split = component.split(SUBCKT_DIVIDER)
            modified_path = SUBCKT_DIVIDER.join(component_split[:-1])  # excludes last component
            component = component_split[-1]  # This is the last component to modify

            if modified_path in self.modified_subcircuits:  # See if this was already a modified sub-circuit instance
                sub_circuit = self.modified_subcircuits[modified_path]
            else:
                sub_circuit_original = self.get_subcircuit(modified_path)  # If not will look for it.
                if sub_circuit_original:
                    new_name = sub_circuit_original.name() + '_' + '_'.join(
                        component_split[:-1])  # Creates a new name with the path appended
                    sub_circuit = sub_circuit_original.clone(new_name=new_name)
                    # Memorize that the copy is relative to that particular instance
                    self.modified_subcircuits[modified_path] = sub_circuit
                    # Change the call to the sub-circuit
                    self._set_model_and_value(modified_path, new_name)
                else:
                    raise ComponentNotFoundError(component)
            #  Change the copy of the sub-circuit related to that particular instance.
            sub_circuit._set_model_and_value(component, value)
            return
        # else: This is the generic case where the sub-circuit is changed
        super()._set_model_and_value(component, value)

    def add_instruction(self, instruction: str) -> None:
        """Adds a SPICE instruction to the netlist.

        For example:

        .. code-block:: text

                  .tran 10m ; makes a transient simulation
                  .meas TRAN Icurr AVG I(Rs1) TRIG time=1.5ms TARG time=2.5ms ; Establishes a measuring
                  .step run 1 100, 1 ; makes the simulation run 100 times

        :param instruction:
            Spice instruction to add to the netlist. This instruction will be added at the end of the netlist,
            typically just before the .BACKANNO statement
        :type instruction: str
        :return: Nothing
        """
        if not instruction.endswith(END_LINE_TERM):
            instruction += END_LINE_TERM
        if _is_unique_instruction(instruction):
            # Before adding new instruction, delete previously set unique instructions
            i = 0
            while i < len(self.netlist):
                line = self.netlist[i]
                if _is_unique_instruction(line):
                    self.netlist[i] = instruction
                    break
                else:
                    i += 1
        elif get_line_command(instruction) == '.PARAM':
            raise RuntimeError('The .PARAM instruction should be added using the "set_parameter" method')

        # check whether the instruction is already there (dummy proofing)
        # TODO: if adding a .MODEL or .SUBCKT it should verify if it already exists and update it.
        if instruction not in self.netlist:
            # Insert before backanno instruction
            try:
                line = self.netlist.index(
                    '.backanno\n')  # TODO: Improve this. END of line termination could be differnt and case as well
            except ValueError:
                line = len(self.netlist) - 2  # This is where typically the .backanno instruction is
            self.netlist.insert(line, instruction)

    def remove_instruction(self, instruction) -> None:
        # docstring is in the parent class

        # TODO: Make it more intelligent so it recognizes .models, .param and .subckt
        # Because the netlist is stored containing the end of line terminations and because they are added when they
        # they are added to the netlist.
        if not instruction.endswith(END_LINE_TERM):
            instruction += END_LINE_TERM
        if instruction in self.netlist:
            self.netlist.remove(instruction)
            _logger.info(f'Instruction "{instruction}" removed')
        else:
            _logger.error(f'Instruction "{instruction}" not found.')

    def remove_Xinstruction(self, search_pattern: str) -> None:
        # docstring is in the parent class
        regex = re.compile(search_pattern, re.IGNORECASE)
        i = 0
        instr_removed = False
        while i < len(self.netlist):
            line = self.netlist[i]
            if isinstance(line, str) and regex.match(line):
                del self.netlist[i]
                instr_removed = True
                _logger.info(f'Instruction "{line}" removed')
            else:
                i += 1
        if not instr_removed:
            _logger.error(f'No instruction matching pattern "{search_pattern}" was found')

    def save_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        # docstring is in the parent class
        if isinstance(run_netlist_file, str):
            run_netlist_file = Path(run_netlist_file)
        run_netlist_file = run_netlist_file.with_suffix('.net')
        with open(run_netlist_file, 'w', encoding=self.encoding) as f:
            lines = iter(self.netlist)
            for line in lines:
                if isinstance(line, SpiceCircuit):
                    line.write_lines(f)
                else:
                    # Writes the modified sub-circuits at the end just before the .END clause
                    if line.upper().startswith(".END"):
                        # write here the modified sub-circuits
                        for sub in self.modified_subcircuits.values():
                            sub.write_lines(f)
                    f.write(line)

    def reset_netlist(self, create_blank: bool = False) -> None:
        """
        Removes all previous edits done to the netlist, i.e. resets it to the original state.

        :returns: Nothing
        """
        super().reset_netlist(create_blank)
        self.modified_subcircuits.clear()
        if create_blank:
            lines = ['* netlist generated from spicelib', '.end']
            finished = self._add_lines(lines)
            if not finished:
                raise SyntaxError("Netlist with missing .END or .ENDS statements")
        elif self.netlist_file.exists():
            with open(self.netlist_file, 'r', encoding=self.encoding, errors='replace') as f:
                lines = iter(f)  # Creates an iterator object to consume the file
                finished = self._add_lines(lines)
                if not finished:
                    raise SyntaxError("Netlist with missing .END or .ENDS statements")
                # else:
                #     for _ in lines:  # Consuming the rest of the file.
                #         pass  # print("Ignoring %s" % _)
        else:
            _logger.error("Netlist file not found: {}".format(self.netlist_file))

    @staticmethod
    def find_subckt_in_lib(library, subckt_name) -> Union['SpiceCircuit', None]:
        """
        Finds a sub-circuit in a library. The search is case-insensitive.

        :param library: path to the library to search
        :type library: str
        :param subckt_name: sub-circuit to search for
        :type subckt_name: str
        :return: Returns a SpiceCircuit instance with the sub-circuit found or None if not found
        :rtype: SpiceCircuit
        """
        # 0. Setup things
        reg_subckt = re.compile(SUBCKT_CLAUSE_FIND + subckt_name, re.IGNORECASE)
        # 1. Find Encoding
        encoding = detect_encoding(library)
        #  2. scan the file
        with open(library, encoding=encoding) as lib:
            for line in lib:
                search = reg_subckt.match(line)
                if search:
                    sub_circuit = SpiceCircuit()
                    sub_circuit.netlist.append(line)
                    # Advance to the next non nested .ENDS
                    finished = sub_circuit._add_lines(lib)
                    if finished:
                        return sub_circuit
        #  3. Return an instance of SpiceCircuit
        return None

    def run(self, wait_resource: bool = True,
            callback: Callable[[str, str], Any] = None, timeout: float = None, run_filename: str = None, simulator=None):
        """
        *(Deprecated)*

        Convenience function for maintaining legacy with legacy code. Runs the SPICE simulation.
        """
        from ..sim.sim_runner import SimRunner
        Sim = SimRunner(simulator=simulator)
        return Sim.run(self, wait_resource=wait_resource, callback=callback, timeout=timeout, run_filename=run_filename)
