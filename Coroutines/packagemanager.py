import subprocess
import sys
import shutil
import json
import logging
from typing import List, Dict, Any


# ===================== LOGGER SETUP =====================
logger = logging.getLogger("package_manager")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


# ===================== UTIL HELPERS =====================

def command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    return shutil.which(cmd) is not None


# ===================== PYTHON ENV =====================

def python_available() -> bool:
    return command_exists("python3") or command_exists("python") or command_exists("pip")


def pip_exec() -> str:
    return sys.executable


def list_installed_python_packages() -> List[str]:
    try:
        output = subprocess.check_output([pip_exec(), "-m", "pip", "list"])
        lines = output.decode().splitlines()[2:]  # Skip header
        return [line.split()[0] for line in lines]
    except Exception:
        return []


def is_python_package_installed(package: str) -> bool:
    try:
        subprocess.check_output([pip_exec(), "-m", "pip", "show", package])
        return True
    except subprocess.CalledProcessError:
        return False


def uninstall_python_package(package: str) -> bool:
    try:
        subprocess.check_call([pip_exec(), "-m", "pip", "uninstall", "-y", package])
        logger.info(f"Python package removed: {package}")
        return True
    except subprocess.CalledProcessError:
        logger.error(f"Failed to remove python package: {package}")
        return False


# ===================== NODE ENV =====================

def node_available() -> bool:
    return command_exists("node") or command_exists("npm")


def list_installed_node_packages() -> List[str]:
    try:
        output = subprocess.check_output(["npm", "list", "-g", "--depth=0"], stderr=subprocess.STDOUT)
        lines = output.decode().splitlines()[1:]  # Skip project root line
        pkgs = []
        for line in lines:
            if "@" in line:
                pkg_name = line.strip().split("@")[0].replace("├── ", "").replace("└── ", "")
                pkgs.append(pkg_name)
        return pkgs
    except Exception:
        return []


def is_node_package_installed(package: str) -> bool:
    try:
        subprocess.check_output(["npm", "list", "-g", package])
        return True
    except subprocess.CalledProcessError:
        return False


def uninstall_node_package(package: str) -> bool:
    try:
        subprocess.check_call(["npm", "uninstall", "-g", package])
        logger.info(f"Node package removed: {package}")
        return True
    except subprocess.CalledProcessError:
        logger.error(f"Failed to remove node package: {package}")
        return False


# ===================== UNUSED PACKAGE SCAN =====================

def scan_unused_packages(used_packages: List[str], installed_packages: List[str]) -> List[str]:
    """Return packages that are installed but not in the used list."""
    return [pkg for pkg in installed_packages if pkg not in used_packages]


# ===================== WRAPPER FUNCTION =====================

def run_package_cleanup(
    remove_packages: List[str],
    used_python_packages: List[str] = None,
    used_node_packages: List[str] = None
) -> Dict[str, Any]:
    """
    Wrapper that:
    - Checks env availability
    - Removes requested packages
    - Scans unused packages
    - Returns JSON for DB logging
    """

    result = {
        "python": {
            "env_available": python_available(),
            "packages_checked": [],
            "packages_removed": [],
            "packages_not_found": [],
            "unused_packages": [],
        },
        "node": {
            "env_available": node_available(),
            "packages_checked": [],
            "packages_removed": [],
            "packages_not_found": [],
            "unused_packages": [],
        }
    }

    # ----------------------------------- PYTHON -----------------------------------
    if python_available():
        logger.info("Python environment found.")
        installed_py = list_installed_python_packages()

        for pkg in remove_packages:
            result["python"]["packages_checked"].append(pkg)
            if is_python_package_installed(pkg):
                if uninstall_python_package(pkg):
                    result["python"]["packages_removed"].append(pkg)
            else:
                result["python"]["packages_not_found"].append(pkg)

        if used_python_packages:
            unused_py = scan_unused_packages(used_python_packages, installed_py)
            result["python"]["unused_packages"] = unused_py

    else:
        logger.warning("Python environment not found.")

    # ----------------------------------- NODE -----------------------------------
    if node_available():
        logger.info("Node environment found.")
        installed_node = list_installed_node_packages()

        for pkg in remove_packages:
            result["node"]["packages_checked"].append(pkg)
            if is_node_package_installed(pkg):
                if uninstall_node_package(pkg):
                    result["node"]["packages_removed"].append(pkg)
            else:
                result["node"]["packages_not_found"].append(pkg)

        if used_node_packages:
            unused_node = scan_unused_packages(used_node_packages, installed_node)
            result["node"]["unused_packages"] = unused_node

    else:
        logger.warning("Node environment not found.")

    return result


# ===================== SAMPLE USAGE =====================
if __name__ == "__main__":
    output = run_package_cleanup(
        remove_packages=["requests", "express"],   # Multiple packages
        used_python_packages=["pip", "setuptools"],
        used_node_packages=["npm"]
    )
    print(json.dumps(output, indent=4))
