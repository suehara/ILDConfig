import importlib.abc
import importlib.util
import math
import os
import re
import xml.etree.ElementTree as ET
from importlib.machinery import SourceFileLoader
from io import TextIOWrapper
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def import_from(
    filename: Union[str, os.PathLike],
    module_name: Optional[str] = None,
    global_vars: Optional[Dict[str, Any]] = None,
) -> Any:
    """Dynamically imports a module from the specified file path.

    This function imports a module from a given filename, with the option to
    specify the module's name and inject global variables into the module before
    it is returned. If `module_name` is not provided, the filename is used as
    the module name after replacing '.' with '_'. Global variables can be passed
    as a dictionary to `global_vars`, which will be injected into the module's
    namespace.

    Args:
        filename (str): The path to the file from which to import the module.
        module_name (Optional[str]): The name to assign to the module. Defaults
            to None, in which case the filename is used as the module name.
        global_vars (Optional[Dict[str, Any]]): A dictionary of global variables
            to inject into the module's namespace. Defaults to None.

    Returns:
        Any: The imported module with the specified modifications.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ImportError: If there is an error during the import process.

    """
    filename = os.path.abspath(filename)
    if not os.path.exists(filename):
        raise FileNotFoundError(f"No such file: '{filename}'")

    module_name = module_name or os.path.basename(filename).replace(".", "_")
    loader = SourceFileLoader(module_name, filename)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    if global_vars:
        module.__dict__.update(global_vars)
    loader.exec_module(module)
    return module


def load_file(opt_file: Union[TextIOWrapper, str, os.PathLike]) -> None:
    """Loads and executes the content of a given file in the current interpreter session.

    This function takes a file object or a path to a file, reads its content,
    and then executes it as Python code within the global scope of the current
    interpreter session. If `opt_file` is a file handle it will not be closed.

    Args:
        opt_file (Union[TextIOWrapper, str, os.PathLike]): A file object or a
                                                           path to the file that
                                                           contains Python code
                                                           to be executed.

    Raises:
        FileNotFoundError: If `opt_file` is a path and no file exists at that path.
        IOError: If there's an error opening or reading the file.
        SyntaxError: If there's a syntax error in the code being executed.
        Exception: Any exception raised by the executed code will be propagated.

    """
    if isinstance(opt_file, (str, os.PathLike)):
        with open(opt_file, "r") as file:
            code = compile(file.read(), file.name, "exec")
    else:
        code = compile(opt_file.read(), opt_file.name, "exec")

    exec(code, globals())


class SequenceLoader:
    """A class for loading algorithm sequences onto a list of algorithms

    It dynamically loads algorithms from Python files based on the given
    sequence names. In the import process it will look for a Sequence of
    algorithms which might have configuration constants that depend on some
    global calibration configuration. These constants are provided during the
    import of a sequence, such that the imported python files do not need to
    define all of them.
    """

    def __init__(self, alg_list: list, global_vars: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the SequenceLoader

        This initializes a SequenceLoader with the list of algorithms to which
        dynamically loaded algorithms should be appended to. It optionally takes
        some global calibration constants that should be injected during import
        of the sequence files

        Args:
            alg_list (List): A list to store loaded sequence algorithms.
            global_vars (Optional[Dict[str, Any]]): A dictionary of global
                variables for the sequences. Defaults to None. The keys in this
                dictionary will be the available variables in the imported
                module and the values will be the values of these variables.
        """
        self.alg_list = alg_list
        self.global_vars = global_vars

    def load(self, sequence: str) -> None:
        """Loads a sequence algorithm from a specified Python file and appends
        it to the algorithm list

        The method constructs the filename from the sequence parameter name and
        imports the sequence from the imported module.

        Args:
            sequence (str): The name of the sequence to load. The sequence name
                should correspond to a Python file and class name following the
                pattern `{sequence}.py` and `{sequence}Sequence`, respectively.

        Examples:
            >>> alg_list = []
            >>> seq_loader = SequenceLoader(alg_list)
            >>> seq_loader.load("Tracking/TrackingDigi")

            This will import the file `Tracking/TrackingDigi.py` and add the
            sequence of algorithms that is defined in `TrackingDigiSequence` in
            that file to the alg_list
        """
        filename = f"{sequence}.py"
        seq_name = f"{sequence.split('/')[-1]}Sequence"

        seq_module = import_from(
            filename,
            global_vars=self.global_vars,
        )

        seq = getattr(seq_module, seq_name)
        self.alg_list.extend(seq)


def parse_collection_patch_file(patch_file: Union[str, os.PathLike]) -> List[str]:
    """Parse a collection patch file such that it can be used by the
    PatchCollections processor.

    This function reads the file that has been passed in and effectively
    flattens its contents into one list of strings. The main assumption is that
    the file has been produced via `check_missing_colls --minimal <...>` in
    which case it can be directly consumed. Note that no real error checking is
    done to detect malformed inputs in which case something else at a later
    stage will most likely break.

    Args:
        patch_file (Union[str, os.PathLike]): The path to the file that should
                                              be parsed

    Returns:
        List[str]: A list of strings (pairs of "names" and "types") that can be
                   consumed by the PatchCollections processor

    """
    with open(patch_file, "r") as pfile:
        patch_colls = [l.split() for l in pfile.readlines()]

    # Flatten the list of lists into one large list
    return [s for strings in patch_colls for s in strings]


def get_drop_collections(calib: Dict[str, str], cmds: bool) -> List[str]:
    """Get the collections to drop from the calibration

    Combine all the different sources for dropping collections into one list.
    These sources are
    - DropCollectionsCalibrationREC (i.e. the ones defined in the calibration)
    - AdditionalDropCollectionsREC (i.e. user defined ones)

    Args:
        calib (Dict[str, str]): The calibration configuration
        cmds (bool): Whether or not the list should be turned into a list of
            keep / drop commands as used by EDM4hep output

    Returns:
        List [str]: A list of collections to drop
    """
    drop_calib = calib.get("DropCollectionsCalibrationREC", "")
    drop_calib = drop_calib.split(" ") if drop_calib else []
    drop_add = calib.get("AdditionalDropCollectionsREC", "")
    drop_add = drop_add.split(" ") if drop_add else []

    prefix = "drop " if cmds else ""
    return [f"{prefix}{c}" for c in drop_calib + drop_add]


# Units that appear in the compact file constants, expressed in the units that
# are used by the reconstruction (mm, tesla, rad, GeV, ns)
_COMPACT_UNITS = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "um": 1e-3,
    "micrometer": 1e-3,
    "nm": 1e-6,
    "tesla": 1.0,
    "kilogauss": 0.1,
    "gauss": 1e-4,
    "rad": 1.0,
    "radian": 1.0,
    "mrad": 1e-3,
    "deg": math.pi / 180.0,
    "degree": math.pi / 180.0,
    "pi": math.pi,
    "twopi": 2.0 * math.pi,
    "GeV": 1.0,
    "MeV": 1e-3,
    "keV": 1e-6,
    "eV": 1e-9,
    "TeV": 1e3,
    "ns": 1.0,
    "us": 1e3,
    "ms": 1e6,
    "s": 1e9,
}
_COMPACT_FUNCTIONS = {
    name: getattr(math, name)
    for name in (
        "sin",
        "cos",
        "tan",
        "asin",
        "acos",
        "atan",
        "atan2",
        "sqrt",
        "exp",
        "log",
        "log10",
        "pow",
        "fabs",
        "floor",
        "ceil",
    )
}
_COMPACT_FUNCTIONS.update({"abs": abs, "min": min, "max": max})
# identifiers (constants, units, functions), but not the exponent of a float literal like 1e-3
_COMPACT_IDENTIFIER = re.compile(r"(?<![0-9.])[A-Za-z_][A-Za-z0-9_]*")


class CompactConstants:
    """Minimal resolver for the ``<constant>`` definitions of a DD4hep compact file

    This parses the compact file and (recursively) all files that it includes
    via ``<include ref="..."/>`` and collects the ``<constant name="..."
    value="..."/>`` definitions as well as the ``<field>`` definitions. The
    constants can then be evaluated numerically (in mm, tesla, rad, GeV, ns),
    following the usual DD4hep expression syntax (constants referring to other
    constants, units, basic arithmetic and math functions).

    This does not build any geometry and is therefore cheap enough to be used
    at configuration time, e.g. to extract the nominal magnetic field or the
    calorimeter envelope dimensions for algorithms that need them as
    properties.
    """

    def __init__(self, compact_file: Union[str, os.PathLike]) -> None:
        """Parse the compact file and all its includes

        Args:
            compact_file (Union[str, os.PathLike]): The compact file to parse
        """
        self.constants: Dict[str, str] = {}
        self.fields: List[Dict[str, str]] = []
        self._values: Dict[str, float] = {}
        self._visited = set()
        self._parse(Path(os.path.expandvars(str(compact_file))))

    def _parse(self, path: Path) -> None:
        path = path.resolve()
        if path in self._visited or not path.is_file():
            return
        self._visited.add(path)
        for elem in ET.parse(path).getroot().iter():
            if elem.tag == "include" and "ref" in elem.attrib:
                ref = Path(os.path.expandvars(elem.attrib["ref"]))
                self._parse(ref if ref.is_absolute() else path.parent / ref)
            elif elem.tag == "constant" and "name" in elem.attrib and "value" in elem.attrib:
                # The first definition wins (same as the order in which DD4hep processes the file)
                self.constants.setdefault(elem.attrib["name"], elem.attrib["value"])
            elif elem.tag == "field":
                self.fields.append(dict(elem.attrib))

    def evaluate(self, expression: str) -> float:
        """Evaluate an expression that may use constants, units and math functions

        Args:
            expression (str): The expression to evaluate, e.g. ``"TPC_outer_radius + 35*mm"``

        Returns:
            float: The numerical value in mm / tesla / rad / GeV / ns
        """

        def _replace(match: re.Match) -> str:
            name = match.group(0)
            if name in _COMPACT_FUNCTIONS:
                return name
            if name in _COMPACT_UNITS:
                return repr(_COMPACT_UNITS[name])
            if name in self.constants:
                return f"({self.get(name)!r})"
            raise KeyError(f"Unknown constant or unit '{name}' in expression '{expression}'")

        expr = _COMPACT_IDENTIFIER.sub(_replace, expression.replace("^", "**"))
        return float(eval(expr, {"__builtins__": {}}, _COMPACT_FUNCTIONS))

    def get(self, name: str) -> float:
        """Get the numerical value of a constant

        Args:
            name (str): The name of the constant

        Returns:
            float: The numerical value in mm / tesla / rad / GeV / ns
        """
        if name not in self._values:
            if name not in self.constants:
                raise KeyError(f"Constant '{name}' is not defined in the compact file")
            self._values[name] = self.evaluate(self.constants[name])
        return self._values[name]

    def solenoid_field_tesla(self) -> float:
        """Get the nominal (central) solenoid field in tesla

        This uses the ``inner_field`` of the first ``<field type="solenoid">``
        definition. Models that use a field map instead fall back to the
        ``Field_nominal_value`` or ``SolenoidField`` constants.

        Returns:
            float: The nominal solenoid field in tesla
        """
        for field in self.fields:
            if field.get("type") == "solenoid" and "inner_field" in field:
                return self.evaluate(field["inner_field"])
        for name in ("Field_nominal_value", "SolenoidField"):
            if name in self.constants:
                return self.get(name)
        raise KeyError("Could not determine the solenoid field from the compact file")


def _append_commas_expect_last(config_list, list_to_add):
    """Append a comma to each string in the list except the last one."""
    config_list.extend([f"{ele}," for ele in list_to_add[:-1]] + [list_to_add[-1]])


def encode_CT_steps_dict_to_legacy_list(steps_dict: dict) -> list[str]:
    """
    Encode the conformal tracking configuration into the list of strings that is expected by the Marlin processor
    """
    legacy_list = []

    # Loop over steps
    for step_name, step in steps_dict.items():
        legacy_list.append(f"[{step_name}]")

        # Collections
        legacy_list.extend(["@Collections", ":"])
        _append_commas_expect_last(legacy_list, step.get("collections"))

        # Parameters
        legacy_list.extend(["@Parameters", ":"])
        for key, value in step.get("params", {}).items():
            if key in ["SlopeZRange", "HighPTCut"]:
                legacy_list.append(f"{key}:")
            else:
                legacy_list.append(str(key))
                legacy_list.append(":")
            legacy_list.append(f"{value};")

        # Flags
        flags = step.get("flags", [])
        if flags:
            legacy_list.extend(["@Flags", ":"])
            _append_commas_expect_last(legacy_list, flags)

        # Functions
        functions = step.get("functions", [])
        if functions:
            legacy_list.extend(["@Functions", ":"])
            _append_commas_expect_last(legacy_list, functions)

    return legacy_list
