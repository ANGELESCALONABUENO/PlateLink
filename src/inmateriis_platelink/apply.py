"""Apply a reviewed installed plate through the host's normal bed selector."""
from .core import BED_TYPES


def apply_installed_bed(expected, fresh, host, host_api):
    installed = fresh.get("review", {}).get("installed")
    if not installed or installed != expected:
        raise ValueError("La placa o su cara cambiaron; revisa nuevamente antes de aplicar")
    bed = installed.get("bed_type")
    if bed not in BED_TYPES:
        raise ValueError("Relaciona primero esta superficie con un tipo de cama de Orca")
    return host_api.preset.project.select_bed_type(bed_type=bed,
        expected_printer=host["printer"], expected_current=host["bed_type"])


def sync_installed_bed(fresh, host, host_api):
    """Select a mapped installed bed on opening/refreshing the native window.

    The browser dashboard has no project selector. Missing mappings remain for
    the operator to resolve; a matching bed does not dirty the project again.
    """
    installed = fresh.get("review", {}).get("installed")
    if not host.get("can_select_bed") or not installed:
        return None
    bed = installed.get("bed_type")
    if bed not in BED_TYPES or bed == host.get("bed_type"):
        return None
    return apply_installed_bed(installed, fresh, host, host_api)
