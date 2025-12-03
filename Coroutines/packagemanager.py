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
    return shutil.which(cmd) is not None


def run_and_get_output(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
    except Exception:
        return ""


# ===================== VERSION HELPERS =====================

def get_python_version() -> str:
    return run_and_get_output([sys.executable, "--version"])


def get_pip_version() -> str:
    return run_and_get_output([sys.executable, "-m", "pip", "--version"])


def get_node_version() -> str:
    return run_and_get_output(["node", "--version"])


def get_npm_version() -> str:
    return run_and_get_output(["npm", "--version"])


# ===================== PYTHON ENV =====================

def python_available() -> bool:
    return command_exists("python3") or command_exists("python") or command_exists("pip")


def pip_exec() -> str:
    return sys.executable


def list_installed_python_packages() -> Dict[str, str]:
    """
    Returns dict: { package: version }
    """
    try:
        output = subprocess.check_output([pip_exec(), "-m", "pip", "list"]).decode()
        lines = output.splitlines()[2:]  # Skip header
        packages = {}
        for line in lines:
            cols = line.split()
            if len(cols) >= 2:
                packages[cols[0]] = cols[1]
        return packages
    except Exception:
        return {}


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


def list_installed_node_packages() -> Dict[str, str]:
    """
    Returns dict: { package: version }
    """
    try:
        output = subprocess.check_output(["npm", "list", "-g", "--depth=0"], stderr=subprocess.STDOUT).decode()
        lines = output.splitlines()[1:]  # Skip first line
        packages = {}
        for line in lines:
            if "@" in line:
                pkg = line.strip().replace("├── ", "").replace("└── ", "")
                name, version = pkg.split("@")
                packages[name] = version
        return packages
    except Exception:
        return {}


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

def scan_unused_packages(used_packages: List[str], installed_packages: Dict[str, str]) -> List[str]:
    return [pkg for pkg in installed_packages.keys() if pkg not in used_packages]


# ===================== WRAPPER FUNCTION =====================

def run_package_cleanup(
    remove_packages: List[str],
    used_python_packages: List[str] = None,
    used_node_packages: List[str] = None
) -> Dict[str, Any]:

    result = {
        "version_info": {
            "python": get_python_version(),
            "pip": get_pip_version(),
            "node": get_node_version(),
            "npm": get_npm_version(),
        },
        "installed_packages": {
            "python": {},
            "node": {},
        },
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
        result["installed_packages"]["python"] = installed_py

        for pkg in remove_packages:
            result["python"]["packages_checked"].append(pkg)

            if is_python_package_installed(pkg):
                if uninstall_python_package(pkg):
                    result["python"]["packages_removed"].append(pkg)
            else:
                result["python"]["packages_not_found"].append(pkg)

        if used_python_packages:
            result["python"]["unused_packages"] = scan_unused_packages(
                used_python_packages, installed_py
            )
    else:
        logger.warning("Python environment not found.")

    # ----------------------------------- NODE -----------------------------------
    if node_available():
        logger.info("Node environment found.")
        installed_node = list_installed_node_packages()
        result["installed_packages"]["node"] = installed_node

        for pkg in remove_packages:
            result["node"]["packages_checked"].append(pkg)

            if is_node_package_installed(pkg):
                if uninstall_node_package(pkg):
                    result["node"]["packages_removed"].append(pkg)
            else:
                result["node"]["packages_not_found"].append(pkg)

        if used_node_packages:
            result["node"]["unused_packages"] = scan_unused_packages(
                used_node_packages, installed_node
            )
    else:
        logger.warning("Node environment not found.")

    return result


# ===================== SAMPLE USAGE =====================
if __name__ == "__main__":
    output = run_package_cleanup(
        remove_packages=["requests", "express"],
        used_python_packages=["pip", "setuptools"],
        used_node_packages=["npm"]
    )
    print(json.dumps(output, indent=4))
