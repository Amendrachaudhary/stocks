"""
setup.py - Native C-Extension Compilation Configuration (Cython)
================================================================
Compiles internal core modules (adapters.py, router.py, encryption.py)
into high-performance, tamper-resistant native C-extension shared objects (.so).
"""

from pathlib import Path
from setuptools import setup, Extension
from Cython.Build import cythonize

BASE_DIR = Path(__file__).resolve().parent

# Define native extensions for internal proprietary modules
extensions = [
    Extension(
        name="adapters",
        sources=[str(BASE_DIR / "adapters.py")]
    ),
    Extension(
        name="router",
        sources=[str(BASE_DIR / "router.py")]
    ),
    Extension(
        name="encryption",
        sources=[str(BASE_DIR / "encryption.py")]
    ),
]

setup(
    name="fno_automation_native",
    version="1.0.0",
    description="High-performance native C-extensions for FNO Trading Automation Suite",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "binding": True,
            "embedsignature": True
        },
        annotate=False
    )
)
