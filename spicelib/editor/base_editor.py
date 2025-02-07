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
# Name:        base_editor.py
# Purpose:     Abstract class that defines the protocol for the editors
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

__author__ = "Nuno Brum"
__version__ = "0.1.0"


from abc import ABC, abstractmethod
from collections import OrderedDict
from math import floor, log
from pathlib import Path
from typing import Union
import logging


__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2021, Fribourg Switzerland"

_logger = logging.getLogger("spicelib.BaseEditor")

SUBCKT_DIVIDER = ':'  #: This controls the sub-circuit divider when setting component values inside sub-circuits.
# Ex: Editor.set_component_value('XU1:R1', '1k')

UNIQUE_SIMULATION_DOT_INSTRUCTIONS = ('.AC', '.DC', '.TRAN', '.NOISE', '.DC', '.TF')
SPICE_DOT_INSTRUCTIONS = (
    '.BACKANNO',
    '.END',
    '.ENDS',
    '.FERRET',  # Downloads a File from a given URL
    '.FOUR',  # Compute a Fourier Component after a .TRAN Analysis
    '.FUNC', '.FUNCTION',
    '.GLOBAL',
    '.IC',
    '.INC', '.INCLUDE',  # Include another file
    '.LIB',  # Include a Library
    '.LOADBIAS',  # Load a Previously Solved DC Solution
    # These Commands are part of the contraption Programming Language of the Arbitrary State Machine
    '.MACHINE', '.STATE', '.RULE', '.OUTPUT', '.ENDMACHINE',
    '.MEAS', '.MEASURE',
    '.MODEL',
    '.NET',  # Compute Network Parameters in a .AC Analysis
    '.NODESET',  # Hints for Initial DC Solution
    '.OP',
    '.OPTIONS',
    '.PARAM', '.PARAMS',
    '.SAVE', '.SAV',
    '.SAVEBIAS',
    '.STEP',
    '.SUBCKT',
    '.TEXT',
    '.WAVE',  # Write Selected Nodes to a .Wav File

)
PARAM_REGEX = r"(?<= )(?P<replace>%s(\s*=\s*)(?P<value>[\w\*\/\.\+\-\/\*\{\}\(\)\t ]*))(?<!\s)($|\s+)(?!\s*=)"


def format_eng(value) -> str:
    """
    Helper function for formatting value with the SI qualifiers.  That is, it will use

        * p for pico (10E-12)
        * n for nano (10E-9)
        * u for micro (10E-6)
        * m for mili (10E-3)
        * k for kilo (10E+3)
        * Meg for Mega (10E+6)


    :param value: float value to format
    :type value: float
    :return: String with the formatted value
    :rtype: str
    """
    if value == 0.0:
        return "{:g}".format(value)  # This avoids a problematic log(0), and the int and float conversions
    e = floor(log(abs(value), 1000))
    if -5 <= e < 0:
        suffix = "fpnum"[e]
    elif e == 0:
        return "{:g}".format(value)
    elif e == 1:
        suffix = "k"
    elif e == 2:
        suffix = 'Meg'
    else:
        return '{:E}'.format(value)
    return '{:g}{:}'.format(value * 1000 ** -e, suffix)


def scan_eng(value: str) -> float:
    """
    Converts a string to a float, considering SI multipliers

        * f for femto (10E-15)
        * p for pico (10E-12)
        * n for nano (10E-9)
        * u or µ for micro (10E-6)
        * m for mili (10E-3)
        * k or K for kilo (10E+3)
        * Meg for Mega (10E+6)

    The extra unit qualifiers such as V for volts or F for Farads are ignored.


    :param value: string to be converted to float
    :type value: str
    :return:
    :rtype: float
    :raises: ValueError when the value cannot be converted.
    """
    # Search for the last digit on the string. Assuming that all after the last number are SI qualifiers and units.
    value = value.strip()
    x = len(value)
    while x > 0:
        if value[x - 1] in "0123456789":
            break
        x -= 1
    suffix = value[x:]  # this is the non-numeric part at the end
    f = float(value[:x])  # this is the numeric part. Can raise ValueError.
    if suffix:
        if suffix[0] in "fpnuµmkK":
            return f * {
                'f': 1.0e-15,
                'p': 1.0e-12,
                'n': 1.0e-09,
                'u': 1.0e-06,
                'µ': 1.0e-06,
                'm': 1.0e-03,
                'k': 1.0e+03,
                'K': 1.0e+03,  # LTSpice uses the capital K for Kilo
            }[suffix[0]]
        elif suffix.upper().startswith("MEG"):
            return f * 1E+6
    return f


class ComponentNotFoundError(Exception):
    """Component Not Found Error"""


class ParameterNotFoundError(Exception):
    """ParameterNotFound Error"""

    def __init__(self, parameter):
        super().__init__(f'Parameter "{parameter}" not found')


class Component(object):
    """Hols component information"""

    def __init__(self):
        self.reference = ""
        self.attributes = OrderedDict()
        self.ports = []


class BaseEditor(ABC):
    """
    This defines the primitives (protocol) to be used for both SpiceEditor and AscEditor
    classes.
    """

    @property
    @abstractmethod
    def circuit_file(self) -> Path:
        """Returns the path of the circuit file."""
        ...

    @abstractmethod
    def reset_netlist(self, create_blank: bool = False) -> None:
        """
        Reverts all changes done to the netlist. If create_blank is set to True, then the netlist is blanked.

        :param create_blank: If True, the netlist will be reset to a new empty netlist. If False, the netlist will be
                             reset to the original state.
        """
        ...

    @abstractmethod
    def save_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        """
        Saves the current state of the netlist to a file.

        :param run_netlist_file: File name of the netlist file.
        :type run_netlist_file: Path or str
        :returns: Nothing
        """
        ...

    def write_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        """
        (Deprecated)

        Writes the netlist to a file. This is an alias to save_netlist."""
        self.save_netlist(run_netlist_file)

    @abstractmethod
    def get_component(self, reference: str) -> Component:
        """Returns the Component object representing the given reference in the netlist."""
        ...

    @abstractmethod
    def get_subcircuit(self, reference: str) -> 'BaseEditor':
        """Returns a hierarchical subdesign"""
        ...

    def get_component_attribute(self, reference: str, attribute: str) -> str:
        """Returns the value of the attribute of the component.
        :param reference: Reference of the component
        :type reference: str
        :param attribute: Name of the attribute to be retrieved
        :type attribute: str
        :return: Value of the attribute being sought
        :rtype: str
        :raises: ComponentNotFoundError - In case the component is not found
                 KeyError - In case the attribute is not found
        """
        return self.get_component(reference).attributes[attribute]

    def get_component_nodes(self, reference: str) -> list:
        """Returns the value of the port of the component.
        :param reference: Reference of the component
        :type reference: str
        :return: List with the ports of the component
        :rtype: str
        :raises: ComponentNotFoundError - In case the component is not found
                 KeyError - In case the port is not found
        """
        return self.get_component(reference).ports

    def get_component_info(self, reference) -> dict:
        """
        Retrieves the component information. This is a dictionary with the component information. This method is
        deprecated and will be removed in future versions. Use get_component_attribute instead.

        :param reference: Reference of the component
        :type reference: str
        :return: Dictionary with the component information
        :rtype: dict
        :raises: UnrecognizedSyntaxError when the line doesn't match the expected REGEX. NotImplementedError of there
                 isn't an associated regular expression for the component prefix.
        """
        return self.get_component(reference).attributes

    @abstractmethod
    def get_parameter(self, param: str) -> str:
        """
        Retrieves a Parameter from the Netlist

        :param param: Name of the parameter to be retrieved
        :type param: str
        :return: Value of the parameter being sought
        :rtype: str
        :raises: ParameterNotFoundError - In case the component is not found
        """
        ...

    def set_parameter(self, param: str, value: Union[str, int, float]) -> None:
        """Adds a parameter to the SPICE netlist.

        Usage: ::

         editor.set_parameter("TEMP", 80)

        This adds onto the netlist the following line: ::

         .PARAM TEMP=80

        This is an alternative to the set_parameters which is more pythonic in it's usage,
        and allows setting more than one parameter at once.

        :param param: Spice Parameter name to be added or updated.
        :type param: str

        :param value: Parameter Value to be set.
        :type value: str, int or float

        :return: Nothing
        """
        ...

    def set_parameters(self, **kwargs):
        """Adds one or more parameters to the netlist.
        Usage: ::

            for temp in (-40, 25, 125):
                for freq in sweep_log(1, 100E3,):
                    editor.set_parameters(TEMP=80, freq=freq)

        :key param_name:
            Key is the parameter to be set. values the ther corresponding values. Values can either be a str; an int or
            a float.

        :returns: Nothing
        """
        for param in kwargs:
            self.set_parameter(param, kwargs[param])

    @abstractmethod
    def set_component_value(self, device: str, value: Union[str, int, float]) -> None:
        """Changes the value of a component, such as a Resistor, Capacitor or Inductor. For components inside
        subcircuits, use the subcirciut designator prefix with ':' as separator (Example X1:R1)
        Usage: ::

            editor.set_component_value('R1', '3.3k')
            editor.set_component_value('X1:C1', '10u')

        :param device: Reference of the circuit element to be updated.
        :type device: str
        :param value:
            value to be be set on the given circuit element. Float and integer values will automatically
            formatted as per the engineering notations 'k' for kilo, 'm', for mili and so on.
        :type value: str, int or float
        :raises:
            ComponentNotFoundError - In case the component is not found

            ValueError - In case the value doesn't correspond to the expected format

            NotImplementedError - In case the circuit element is defined in a format which is not supported by this
            version.

            If this is the case, use GitHub to start a ticket.  https://github.com/nunobrum/spicelib
        """
        ...

    @abstractmethod
    def set_element_model(self, element: str, model: str) -> None:
        """Changes the value of a circuit element, such as a diode model or a voltage supply.
        Usage: ::

            editor.set_element_model('D1', '1N4148')
            editor.set_element_model('V1' "SINE(0 1 3k 0 0 0)")

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
        ...

    @abstractmethod
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
        ...

    def get_component_floatvalue(self, element: str) -> float:
        """
        Returns the value of a component retrieved from the netlist.

        :param element: Reference of the circuit element to get the value in float format.
        :type element: str

        :return: value of the circuit element in float type
        :rtype: float

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        return scan_eng(self.get_component_value(element))

    def set_component_values(self, **kwargs):
        """
        Adds one or more components on the netlist. The argument is in the form of a key-value pair where each
        component designator is the key and the value is value to be set in the netlist.

        Usage 1: ::

         editor.set_component_values(R1=330, R2="3.3k", R3="1Meg", V1="PWL(0 1 30m 1 30.001m 0 60m 0 60.001m 1)")

        Usage 2: ::

         value_settings = {'R1': 330, 'R2': '3.3k', 'R3': "1Meg", 'V1': 'PWL(0 1 30m 1 30.001m 0 60m 0 60.001m 1)'}
         editor.set_component_values(**value_settings)

        :key <comp_ref>:
            The key is the component designator (Ex: V1) and the value is the value to be set. Values can either be
            strings; integers or floats

        :return: Nothing
        :raises: ComponentNotFoundError - In case one of the component is not found.
        """
        for value in kwargs:
            self.set_component_value(value, kwargs[value])

    @abstractmethod
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
        ...

    @abstractmethod
    def add_component(self, component: Component, **kwargs) -> None:
        """
        Adds a component to the design. If the component already exists, it will be replaced by the new one.
        kwargs can be used to add additional parameters to the component. For example, to add a symbol or position.

        :param component: Component to be added to the design.
        :type component: Component

        :return: Nothing
        """
        ...

    @abstractmethod
    def remove_component(self, designator: str) -> None:
        """
        Removes a component from  the design.
        Note: Current implementation only allows removal of a component from the main netlist, not from a sub-circuit.

        :param designator: Component reference in the design. Ex: V1, C1, R1, etc...
        :type designator: str

        :return: Nothing
        :raises: ComponentNotFoundError - When the component doesn't exist on the netlist.
        """
        ...

    @abstractmethod
    def add_instruction(self, instruction: str) -> None:
        """
        Adds a SPICE instruction to the netlist.

        For example:

            .. code-block:: text

                .tran 10m ; makes a transient simulation
                .meas TRAN Icurr AVG I(Rs1) TRIG time=1.5ms TARG time=2.5ms" ; Establishes a measuring
                .step run 1 100, 1 ; makes the simulation run 100 times


        :param instruction:
            Spice instruction to add to the netlist. This instruction will be added at the end of the netlist,
            typically just before the .BACKANNO statement
        :type instruction: str
        :return: Nothing
        """
        ...

    @abstractmethod
    def remove_instruction(self, instruction) -> None:
        """
        Removes a SPICE instruction from the netlist.

        Example:

        .. code-block:: python

            editor.remove_instruction(".STEP run -1 1023 1")

        This only works if the instruction exactly matches the line on the netlist. This means that space characters,
        and upper case and lower case differences will not match the line.

        :param instruction: The list of instructions to remove. Each instruction is of the type 'str'
        :type instruction: str
        :returns: Nothing
        """
        ...

    @abstractmethod
    def remove_Xinstruction(self, search_pattern: str) -> None:
        """
        Removes a SPICE instruction from the netlist based on a search pattern. This is a more flexible way to remove
        instructions from the netlist. The search pattern is a regular expression that will be used to match the
        instructions to be removed. The search pattern will be applied to each line of the netlist and if the pattern
        matches, the line will be removed.

        Example: The code below will remove all AC analysis instructions from the netlist.

        .. code-block:: python

            editor.remove_Xinstruction("\.AC.*")

        :param search_pattern: The list of instructions to remove. Each instruction is of the type 'str'
        :type search_pattern: str
        :returns: Nothing
        """
        ...

    def add_instructions(self, *instructions) -> None:
        """
        Adds a list of instructions to the SPICE NETLIST.

        Example:
        .. code-block:: python

            editor.add_instructions(
                ".STEP run -1 1023 1",
                ".dc V1 -5 5"
            )

        :param instructions: Argument list of instructions to add
        :type instructions: argument list
        :returns: Nothing
        """
        for instruction in instructions:
            self.add_instruction(instruction)
